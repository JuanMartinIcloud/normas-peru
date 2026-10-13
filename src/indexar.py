"""Guarda el TEXTO COMPLETO de cada norma (PDF oficial de El Peruano) y de cada proyecto de ley
(PDF del Congreso) en las BASES DE TEXTO, para el buscador y la IA. El PDF no se guarda.

    python src/indexar.py normas --parte 0 --de 3      # trabajador 1 de 3 para normas
    python src/indexar.py proyectos                     # proyectos de ley

Diseño pensado para la capa gratuita de Neon (100 horas de computo al mes por proyecto):
- La BASE PRINCIPAL (DATABASE_URL) casi no se toca: cada ejecucion la consulta una sola vez al
  empezar (y, para proyectos, una vez al final para guardar sumillas). Asi se apaga sola.
- Todo lo demas (textos, avance de cada trabajador) va a las bases de texto TEXTOS_URL_1..9.
  TEXTOS_URL_1 guarda ademas el avance (tabla "avance").
- Cada documento se identifica con una clave estable que no depende de la base principal:
  normas = hash_unico; proyectos = "periodo|camara|numero".
- Normas: primero las de los ultimos 7 dias que falten; luego hacia atras desde donde quedo.
- Si El Peruano o el Congreso responden con errores, espera cada vez mas antes de seguir.
"""
import argparse
import base64
import os
import re
import time
from datetime import date, timedelta

import psycopg2
import requests
from psycopg2.extras import execute_values

import config
from textos import AGENTE, API_CONGRESO, CABECERAS_CONGRESO, EPDOC, cifrar, texto_pdf

MAX_CARACTERES = 200_000            # texto que se guarda por documento (anexos enormes se recortan)
LIMITE_MB = int(os.getenv("TEXTOS_LIMITE_MB", "940"))   # cada base gratuita de Neon admite 1 GB
PAUSA = {"normas": 1.5, "proyectos": 1.0}
MAX_ERRORES_SEGUIDOS = 12
# Las escrituras se juntan y se envian en bloque cada 20 minutos de reloj (:00, :20, :40), a la vez en
# todos los trabajadores. Asi cada base de texto se enciende unos minutos por bloque y se apaga sola
# el resto del tiempo (Neon cuenta las horas que la base esta encendida).
BLOQUE_SEGUNDOS = 20 * 60
MAX_PENDIENTES = 600
LOTE_NORMAS = 1500                  # normas que lee de la base principal por ejecucion y trabajador
INICIO_HISTORICO = date(2015, 1, 1)

SQL_BASE_TEXTOS = """
DROP TABLE IF EXISTS textos;   -- tabla de una version anterior (clave numerica), ya no se usa
CREATE TABLE IF NOT EXISTS documentos (
    tipo      CHAR(1)     NOT NULL,          -- N = norma, P = proyecto de ley
    clave     TEXT        NOT NULL,          -- normas: hash_unico; proyectos: periodo|camara|numero
    estado    TEXT        NOT NULL,          -- ok | sin_texto (PDF escaneado) | sin_pdf
    texto     TEXT        NOT NULL DEFAULT '',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tipo, clave)
);
CREATE INDEX IF NOT EXISTS idx_documentos_busqueda ON documentos USING GIN (to_tsvector('spanish', texto));
CREATE TABLE IF NOT EXISTS avance (
    trabajador  TEXT PRIMARY KEY,
    cursor      DATE,
    cursor_clave TEXT,
    terminado   BOOLEAN NOT NULL DEFAULT FALSE,
    procesados  INTEGER NOT NULL DEFAULT 0,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_s = requests.Session()


class FuenteNoResponde(Exception):
    pass


# --------------------------------------------------------------------------- bases de texto


class Bases:
    """Conexiones a las bases de texto TEXTOS_URL_1..9 (posicion fija; None si falta)."""

    def __init__(self):
        self.conexiones = []
        for i in range(1, 10):
            url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
            if not url:
                continue
            c = psycopg2.connect(url)
            with c.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(724502)")
                cur.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.tables
                                              WHERE table_schema = 'public' AND table_name = 'documentos')""")
                if not cur.fetchone()[0]:
                    cur.execute(SQL_BASE_TEXTOS)
                cur.execute("ALTER TABLE avance ADD COLUMN IF NOT EXISTS cursor_clave TEXT")
            c.commit()
            self.conexiones.append(c)
        if not self.conexiones:
            raise SystemExit("Faltan los secretos TEXTOS_URL_1, TEXTOS_URL_2... (bases de texto)")
        self.control = self.conexiones[0]
        self.actual = None
        self.pendientes = []          # documentos aun no enviados
        self.avance_pendiente = {}    # trabajador -> (cursor, terminado, procesados, cursor_clave)
        self.bloque = int(time.time() // BLOQUE_SEGUNDOS)

    def tamano_mb(self, c) -> float:
        with c.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database()) / 1048576.0")
            mb = float(cur.fetchone()[0])
        c.commit()
        return mb

    def destino(self):
        """Base con espacio libre (se revisa en cada envio)."""
        for n, c in enumerate(self.conexiones, start=1):
            mb = self.tamano_mb(c)
            if mb < LIMITE_MB:
                if c is not self.actual:
                    print(f"Guardando textos en la base de texto {n} ({mb:.0f} MB usados)")
                self.actual = c
                return c
        raise SystemExit(
            f"::error title=Bases llenas::Todas las bases de texto llegaron a {LIMITE_MB} MB. "
            "Hay que crear otra base gratuita en Neon y agregarla como secreto TEXTOS_URL_<numero>."
        )

    def existentes(self, tipo, claves) -> set:
        """Claves que ya estan guardadas en alguna base de texto."""
        hechas = set()
        if not claves:
            return hechas
        for c in self.conexiones:
            with c.cursor() as cur:
                cur.execute("SELECT clave FROM documentos WHERE tipo = %s AND clave = ANY(%s)", (tipo, list(claves)))
                hechas.update(r[0] for r in cur.fetchall())
            c.commit()
        return hechas

    def guardar(self, tipo, clave, estado, texto):
        self.pendientes.append((tipo, clave, estado, texto))
        self.quizas_enviar()

    def quizas_enviar(self):
        bloque = int(time.time() // BLOQUE_SEGUNDOS)
        if bloque != self.bloque or len(self.pendientes) >= MAX_PENDIENTES:
            self.enviar()
            self.bloque = bloque

    def enviar(self):
        """Escribe en bloque los documentos pendientes y, despues, el avance."""
        if self.pendientes:
            c = self.destino()
            with c.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO documentos (tipo, clave, estado, texto) VALUES %s
                       ON CONFLICT (tipo, clave) DO UPDATE
                       SET estado = EXCLUDED.estado, texto = EXCLUDED.texto, creado_en = now()""",
                    self.pendientes,
                    page_size=50,
                )
            c.commit()
            print(f"  enviados {len(self.pendientes)} documentos a la base de texto")
            self.pendientes = []
        for trabajador, (cursor_fecha, terminado, procesados, cursor_clave) in self.avance_pendiente.items():
            with self.control.cursor() as cur:
                cur.execute(
                    """INSERT INTO avance (trabajador, cursor, cursor_clave, terminado, procesados)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (trabajador) DO UPDATE SET cursor = EXCLUDED.cursor,
                           cursor_clave = EXCLUDED.cursor_clave, terminado = EXCLUDED.terminado,
                           procesados = avance.procesados + EXCLUDED.procesados, actualizado = now()""",
                    (trabajador, cursor_fecha, cursor_clave, terminado, procesados),
                )
            self.control.commit()
        self.avance_pendiente = {}

    def leer_avance(self, trabajador):
        with self.control.cursor() as cur:
            cur.execute("SELECT cursor, cursor_clave, terminado FROM avance WHERE trabajador = %s", (trabajador,))
            fila = cur.fetchone()
        self.control.commit()
        return fila

    def guardar_avance(self, trabajador, cursor_fecha, terminado, procesados, cursor_clave=None):
        """El avance se escribe junto con los documentos (nunca antes que ellos)."""
        previo = self.avance_pendiente.get(trabajador, (None, False, 0, None))
        self.avance_pendiente[trabajador] = (cursor_fecha, terminado, previo[2] + procesados, cursor_clave)

    def cerrar(self):
        try:
            self.enviar()
        finally:
            for c in self.conexiones:
                c.close()


# --------------------------------------------------------------------------- descargas


def pedir(url, **kw) -> requests.Response:
    r = _s.get(url, timeout=120, **kw)
    if r.status_code in (403, 429, 500, 502, 503, 504):
        raise FuenteNoResponde(f"HTTP {r.status_code}")
    return r


def pdf_norma(url_detalle, fecha):
    m = re.search(r"/dispositivo/[A-Z]+/(\d+-\d+)", url_detalle or "")
    if not m:
        return None
    ref = base64.b64encode(f"{m.group(1)}{fecha.strftime('%Y%m%d')}".encode()).decode()
    r = pedir(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE})
    if r.status_code == 404 or r.content[:4] != b"%PDF":
        return None
    return r.content


def expediente_proyecto(periodo, camara, num_pley):
    """Devuelve (sumilla, pdf o None) del proyecto."""
    url = f"{API_CONGRESO}/expediente/{cifrar(periodo)}/{cifrar(num_pley)}"
    r = pedir(url, params={"codTipoParl": camara or "C"}, headers=CABECERAS_CONGRESO)
    if r.status_code == 404:
        return "", None
    exp = (r.json() or {}).get("data") or {}
    sumilla = ((exp.get("general") or {}).get("sumilla") or "").strip()
    segs = sorted(exp.get("seguimientos") or [], key=lambda s: str(s.get("fecha") or ""))
    todos = [a for s in segs for a in (s.get("archivos") or [])]
    utiles = [a for a in todos if a.get("proyectoArchivoId") and a.get("activo") is not False
              and a.get("publico") is not False]
    sin_oficio = [a for a in utiles if not any(
        x in f"{a.get('nombreArchivo')} {a.get('descripcion')}".lower() for x in ("oficio", "cargo", "decreto de remisi"))]
    archivo = (sin_oficio or utiles or [None])[0]
    if not archivo:
        return sumilla, None
    codigo = base64.b64encode(str(archivo["proyectoArchivoId"]).encode()).decode()
    rp = pedir(f"{API_CONGRESO}/archivo/{codigo}/pdf", headers=CABECERAS_CONGRESO)
    if rp.status_code == 404 or rp.content[:4] != b"%PDF":
        return sumilla, None
    return sumilla, rp.content


def extraer(datos) -> str:
    try:
        texto = texto_pdf(datos, MAX_CARACTERES)
    except Exception as e:  # noqa: BLE001  (PDF dañado)
        print(f"    PDF ilegible ({e})")
        texto = ""
    return texto.replace("\x00", "").strip()


# --------------------------------------------------------------------------- principal (solo lectura)


def principal():
    if not config.DATABASE_URL:
        raise SystemExit("Falta DATABASE_URL")
    return psycopg2.connect(config.DATABASE_URL)


def normas_de_principal(desde_fecha, hasta_fecha, parte, de, limite, hasta_clave=None):
    """Normas de esta parte con fecha >= desde y anteriores a (hasta_fecha, hasta_clave), en orden
    descendente por (fecha, hash_unico). Sin hasta_clave: fecha < hasta_fecha."""
    conn = principal()
    try:
        with conn.cursor() as cur:
            if hasta_clave is None:
                limite_sql, params = "fecha < %s", [hasta_fecha]
            else:
                limite_sql, params = "(fecha, hash_unico) < (%s, %s)", [hasta_fecha, hasta_clave]
            cur.execute(
                f"""SELECT hash_unico, fecha, url_detalle FROM normas
                    WHERE fecha >= %s AND {limite_sql} AND url_detalle IS NOT NULL
                      AND abs(hashtext(hash_unico)) %% %s = %s
                    ORDER BY fecha DESC, hash_unico DESC LIMIT %s""",
                [desde_fecha, *params, de, parte, limite],
            )
            return cur.fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- trabajo


class Reloj:
    def __init__(self, minutos):
        self.hasta = time.time() + minutos * 60

    def queda(self):
        return time.time() < self.hasta


def procesar_normas(bases, filas, reloj, estado_errores):
    """Procesa en orden. Devuelve (hechos, ultima_fila_hecha, se_corto): todas las filas hasta
    ultima_fila_hecha (inclusive) quedaron guardadas."""
    hechas = bases.existentes("N", [f[0] for f in filas])
    hechos = 0
    ultima = None
    for fila in filas:
        clave, fecha, url = fila
        if clave not in hechas:
            if not reloj.queda():
                return hechos, ultima, True
            try:
                datos = pdf_norma(url, fecha)
                estado_errores["n"], estado_errores["espera"] = 0, 30
            except (requests.RequestException, FuenteNoResponde) as e:
                estado_errores["n"] += 1
                print(f"  norma {fecha}: {e}; espero {estado_errores['espera']} s")
                time.sleep(estado_errores["espera"])
                estado_errores["espera"] = min(estado_errores["espera"] * 2, 600)
                if estado_errores["n"] >= MAX_ERRORES_SEGUIDOS:
                    print("  El Peruano no responde; se continuara en la proxima ejecucion.")
                return hechos, ultima, True
            if datos is None:
                bases.guardar("N", clave, "sin_pdf", "")
            else:
                texto = extraer(datos)
                ok = len(texto) >= 100
                bases.guardar("N", clave, "ok" if ok else "sin_texto", texto if ok else "")
            hechos += 1
            if hechos % 100 == 0:
                print(f"  {hechos} normas procesadas")
            time.sleep(PAUSA["normas"])
        ultima = fila
    return hechos, ultima, False


def trabajar_normas(parte, de, minutos):
    reloj = Reloj(minutos)
    bases = Bases()
    nombre = f"normas-{parte}-de-{de}"
    errores = {"n": 0, "espera": 30}
    total = 0
    try:
        hoy = date.today()
        # 1) Lo reciente (ultimos 7 dias): siempre se revisa, para indexar lo nuevo de cada dia
        recientes = normas_de_principal(hoy - timedelta(days=7), hoy + timedelta(days=2), parte, de, 5000)
        h, _, _ = procesar_normas(bases, recientes, reloj, errores)
        total += h
        print(f"{nombre}: recientes ({len(recientes)}) revisadas, {h} nuevas")

        # 2) Historico, hacia atras desde donde quedo (cursor = ultima norma guardada en orden)
        fila = bases.leer_avance(nombre)
        if fila and fila[0]:
            cursor_fecha, cursor_clave, terminado = fila[0], fila[1], bool(fila[2])
        else:
            cursor_fecha, cursor_clave, terminado = hoy - timedelta(days=7), None, False
        while reloj.queda() and not terminado:
            lote = normas_de_principal(INICIO_HISTORICO, cursor_fecha, parte, de, LOTE_NORMAS, cursor_clave)
            if not lote:
                terminado = True
                break
            h, ultima, cortado = procesar_normas(bases, lote, reloj, errores)
            total += h
            if ultima is not None:
                cursor_clave, cursor_fecha = ultima[0], ultima[1]
            bases.guardar_avance(nombre, cursor_fecha, False, h, cursor_clave)
            print(f"{nombre}: avanzado hasta {cursor_fecha} ({h} en este tramo)")
            if cortado:
                break
        bases.guardar_avance(nombre, cursor_fecha, terminado, 0, cursor_clave)
    finally:
        print(f"{nombre}: {total} normas procesadas en esta ejecucion")
        bases.cerrar()


def trabajar_proyectos(minutos):
    reloj = Reloj(minutos)
    bases = Bases()
    conn = principal()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT periodo, camara, numero, num_pley, coalesce(titulo, '') FROM proyectos_ley
               WHERE num_pley IS NOT NULL ORDER BY fecha_presentacion DESC NULLS LAST, id DESC"""
        )
        filas = cur.fetchall()
    conn.close()   # la principal se libera mientras se trabaja

    claves = [f"{p}|{c}|{n}" for p, c, n, _, _ in filas]
    hechas = bases.existentes("P", claves)
    pendientes = [(k, f) for k, f in zip(claves, filas) if k not in hechas]
    print(f"Proyectos: {len(filas)} en total, {len(pendientes)} pendientes")
    sumillas = []
    hechos = 0
    errores, espera = 0, 30
    try:
        for clave, (periodo, camara, numero, num_pley, titulo) in pendientes:
            if not reloj.queda():
                break
            try:
                sumilla, datos = expediente_proyecto(periodo, camara, num_pley)
                errores, espera = 0, 30
            except (requests.RequestException, FuenteNoResponde, ValueError) as e:
                errores += 1
                print(f"  proyecto {numero}: {e}; espero {espera} s")
                if errores >= MAX_ERRORES_SEGUIDOS:
                    print("  El Congreso no responde; se continuara en la proxima ejecucion.")
                    break
                time.sleep(espera)
                espera = min(espera * 2, 600)
                continue
            cabecera = "\n".join(x for x in (titulo, sumilla) if x)
            if datos is None:
                bases.guardar("P", clave, "sin_pdf", cabecera)
            else:
                texto = extraer(datos)
                estado = "ok" if len(texto) >= 100 else "sin_texto"
                bases.guardar("P", clave, estado, f"{cabecera}\n\n{texto}".strip())
            sumillas.append((sumilla, periodo, camara, numero))
            hechos += 1
            if hechos % 100 == 0:
                print(f"  {hechos} proyectos procesados")
            time.sleep(PAUSA["proyectos"])
        terminado = hechos >= len(pendientes)
        bases.guardar_avance("proyectos", None, terminado, hechos)
    finally:
        # Las sumillas se guardan en la principal de una sola vez, al final
        if sumillas:
            conn = principal()
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """UPDATE proyectos_ley p SET sumilla = NULLIF(v.sumilla, ''), sumilla_revisada = TRUE
                       FROM (VALUES %s) AS v(sumilla, periodo, camara, numero)
                       WHERE p.periodo = v.periodo AND p.camara = v.camara AND p.numero = v.numero""",
                    sumillas,
                )
            conn.commit()
            conn.close()
        print(f"Proyectos: {hechos} procesados en esta ejecucion")
        bases.cerrar()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tipo", choices=["normas", "proyectos"])
    p.add_argument("--parte", type=int, default=0)
    p.add_argument("--de", type=int, default=1)
    p.add_argument("--max-minutos", type=float, default=50)
    a = p.parse_args()
    if a.tipo == "normas":
        trabajar_normas(a.parte, a.de, a.max_minutos)
    else:
        trabajar_proyectos(a.max_minutos)


if __name__ == "__main__":
    main()
