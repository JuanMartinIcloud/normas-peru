"""Guarda el TEXTO COMPLETO de cada norma (PDF oficial de El Peruano) y de cada proyecto de ley
(PDF del Congreso) en las BASES DE TEXTO, para el buscador y la IA. El PDF no se guarda.

    python src/indexar.py normas --parte 0 --de 3      # trabajador 1 de 3 para normas
    python src/indexar.py proyectos                     # proyectos de ley

Diseño pensado para la capa gratuita de Neon (100 horas de computo al mes por proyecto):
- La BASE PRINCIPAL (DATABASE_URL) casi no se toca: cada ejecucion la consulta una sola vez al
  empezar (y, para proyectos, una vez al final para guardar sumillas). Asi se apaga sola.
- Todo lo demas (textos) va a las bases de texto TEXTOS_URL_2..12 (la 4 es la principal).
  La base 1 se retiro: su contenido se copio integro a la 12. El avance esta en la base 2.
- Cada documento se identifica con una clave estable que no depende de la base principal:
  normas = hash_unico; proyectos = "periodo|camara|numero".
- Normas: primero las de los ultimos 7 dias que falten; luego hacia atras desde donde quedo.
- Si El Peruano o el Congreso responden con errores, espera cada vez mas antes de seguir.
"""
import argparse
import base64
import io
import os
import re
import time
import zlib
from datetime import date, timedelta

import psycopg2
import requests
from bs4 import BeautifulSoup
from psycopg2.extras import execute_values
from pypdf import PdfReader

import config
import ocr as ocr_mod
from textos import AGENTE, API_CONGRESO, CABECERAS_CONGRESO, EPDOC, cifrar, codigo_norma, texto_pdf

MAX_CARACTERES = 200_000            # texto que se guarda por documento (anexos enormes se recortan)
LIMITE_MB = int(os.getenv("TEXTOS_LIMITE_MB", "400"))   # cada base gratuita de Neon admite 512 MB; margen para 15 trabajadores
# Base de texto que guarda la tabla "avance" (la 1 se lleno). La web y el relanzador leen la misma.
CONTROL = int(os.getenv("TEXTOS_CONTROL", "2"))
PAUSA = {"normas": 1.0, "proyectos": 1.0}
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
CREATE INDEX IF NOT EXISTS idx_documentos_busqueda ON documentos USING GIN (to_tsvector('spanish', texto))
    WITH (fastupdate = off);
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
    """Bases de texto TEXTOS_URL_2..12 (la 1 esta retirada).

    No se mantienen conexiones abiertas: Neon apaga la base tras unos minutos sin uso y corta las
    conexiones. Por eso cada operacion abre su propia conexion, la usa y la cierra.
    """

    def __init__(self):
        self.urls = []
        control = ""
        for i in range(1, 13):
            url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
            if i == 1 and os.getenv("TEXTOS_URL_12", "").strip():
                continue   # base 1 retirada (copiada a la 12)
            if url:
                self.urls.append(url)
                if i == CONTROL:
                    control = url
        if not self.urls:
            raise SystemExit("Faltan los secretos TEXTOS_URL_1, TEXTOS_URL_2... (bases de texto)")
        for url in self.urls:
            def preparar(cur):
                cur.execute("SELECT pg_advisory_xact_lock(724502)")
                cur.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.tables
                                              WHERE table_schema = 'public' AND table_name = 'documentos')""")
                if not cur.fetchone()[0]:
                    cur.execute(SQL_BASE_TEXTOS)
                cur.execute("ALTER TABLE avance ADD COLUMN IF NOT EXISTS cursor_clave TEXT")
            self.ejecutar(url, preparar)
        self.control = control or self.urls[0]
        if self.control != self.urls[0]:
            self.mudar_avance(self.urls[0])
        self.actual = None
        self.pendientes = []          # documentos aun no enviados
        self.avance_pendiente = {}    # trabajador -> (cursor, terminado, procesados, cursor_clave)
        self.bloque = int(time.time() // BLOQUE_SEGUNDOS)

    def mudar_avance(self, origen):
        """Copia una sola vez el avance desde la base de texto 1 a la base de control."""
        def contar(cur):
            cur.execute("SELECT count(*) FROM avance")
            return cur.fetchone()[0]
        if self.ejecutar(self.control, contar):
            return
        def leer(cur):
            cur.execute("SELECT trabajador, cursor, cursor_clave, terminado, procesados FROM avance")
            return cur.fetchall()
        filas = self.ejecutar(origen, leer)
        if not filas:
            return
        def copiar(cur):
            execute_values(cur, """INSERT INTO avance (trabajador, cursor, cursor_clave, terminado, procesados)
                                   VALUES %s ON CONFLICT (trabajador) DO NOTHING""", filas)
        self.ejecutar(self.control, copiar)
        print(f"Avance copiado a la base de control ({len(filas)} trabajadores)")

    @staticmethod
    def ejecutar(url, funcion):
        """Abre una conexion, ejecuta funcion(cursor), confirma y cierra. Reintenta si la base
        estaba apagada o corto la conexion."""
        ultimo = None
        for intento in range(4):
            try:
                c = psycopg2.connect(url, connect_timeout=60)
                try:
                    with c.cursor() as cur:
                        resultado = funcion(cur)
                    c.commit()
                    return resultado
                finally:
                    c.close()
            except psycopg2.OperationalError as e:
                ultimo = e
                print(f"  base de texto no respondio ({str(e).strip()[:120]}); reintento {intento + 1}")
                time.sleep(10 * (intento + 1))
        raise ultimo

    def tamano_mb(self, url) -> float:
        def f(cur):
            cur.execute("SELECT pg_database_size(current_database()) / 1048576.0")
            return float(cur.fetchone()[0])
        return self.ejecutar(url, f)

    def destino(self):
        """Base con espacio libre (se revisa en cada envio)."""
        for n, url in enumerate(self.urls, start=1):
            mb = self.tamano_mb(url)
            if mb < LIMITE_MB:
                if url != self.actual:
                    print(f"Guardando textos en la base de texto {n} ({mb:.0f} MB usados)")
                self.actual = url
                return url
        raise SystemExit(
            f"::error title=Bases llenas::Todas las bases de texto llegaron a {LIMITE_MB} MB. "
            "Hay que crear otra base gratuita en Neon y agregarla como secreto TEXTOS_URL_<numero>."
        )

    def existentes(self, tipo, claves) -> set:
        """Claves que ya estan guardadas en alguna base de texto."""
        hechas = set()
        if not claves:
            return hechas
        lista = list(claves)
        for url in self.urls:
            def f(cur):
                cur.execute("SELECT clave FROM documentos WHERE tipo = %s AND clave = ANY(%s)", (tipo, lista))
                return [r[0] for r in cur.fetchall()]
            hechas.update(self.ejecutar(url, f))
        return hechas

    def guardar(self, tipo, clave, estado, texto):
        # Algunos PDF traen caracteres invalidos (p. ej. "surrogates") que la base no acepta: se descartan
        texto = (texto or "").replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")
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
            lote = self.pendientes

            def f(cur):
                execute_values(
                    cur,
                    """INSERT INTO documentos (tipo, clave, estado, texto) VALUES %s
                       ON CONFLICT (tipo, clave) DO UPDATE
                       SET estado = EXCLUDED.estado, texto = EXCLUDED.texto, creado_en = now()""",
                    lote,
                    page_size=50,
                )
            self.ejecutar(self.destino(), f)
            print(f"  enviados {len(lote)} documentos a la base de texto")
            self.pendientes = []
        if self.avance_pendiente:
            avances = list(self.avance_pendiente.items())

            def g(cur):
                for trabajador, (cursor_fecha, terminado, procesados, cursor_clave) in avances:
                    cur.execute(
                        """INSERT INTO avance (trabajador, cursor, cursor_clave, terminado, procesados)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (trabajador) DO UPDATE SET cursor = EXCLUDED.cursor,
                               cursor_clave = EXCLUDED.cursor_clave, terminado = EXCLUDED.terminado,
                               procesados = avance.procesados + EXCLUDED.procesados, actualizado = now()""",
                        (trabajador, cursor_fecha, cursor_clave, terminado, procesados),
                    )
            self.ejecutar(self.control, g)
            self.avance_pendiente = {}

    def leer_avance(self, trabajador):
        def f(cur):
            cur.execute("SELECT cursor, cursor_clave, terminado FROM avance WHERE trabajador = %s", (trabajador,))
            return cur.fetchone()
        return self.ejecutar(self.control, f)

    def limpiar_avance(self, de, prefijo="normas"):
        """Borra el avance de una configuracion anterior (otro numero de trabajadores)."""
        def f(cur):
            cur.execute("DELETE FROM avance WHERE (trabajador = %s OR trabajador LIKE %s) AND trabajador NOT LIKE %s",
                        (prefijo, f"{prefijo}-%", f"%-de-{de}"))
        self.ejecutar(self.control, f)

    def guardar_avance(self, trabajador, cursor_fecha, terminado, procesados, cursor_clave=None):
        """El avance se escribe junto con los documentos (nunca antes que ellos)."""
        previo = self.avance_pendiente.get(trabajador, (None, False, 0, None))
        self.avance_pendiente[trabajador] = (cursor_fecha, terminado, previo[2] + procesados, cursor_clave)

    def cerrar(self):
        self.enviar()


# --------------------------------------------------------------------------- descargas


def pedir(url, **kw) -> requests.Response:
    r = _s.get(url, timeout=120, **kw)
    if r.status_code in (403, 429, 500, 502, 503, 504):
        raise FuenteNoResponde(f"HTTP {r.status_code}")
    return r


def pdf_norma(url_detalle, fecha):
    codigo = codigo_norma(url_detalle)
    if not codigo:
        return None
    ref = base64.b64encode(f"{codigo}{fecha.strftime('%Y%m%d')}".encode()).decode()
    r = pedir(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE})
    if r.status_code == 404 or r.content[:4] != b"%PDF":
        return None
    return r.content


def _es_del_proyecto(archivo, numero) -> bool:
    """El archivo es el texto del proyecto si su nombre es "PL" + su numero (PL_2973, PL 2973,
    PL-2973 o PL0297320220906 = numero con 5 cifras + fecha), sin "y otros" (dictamenes)."""
    nombre = f"{archivo.get('nombreArchivo') or ''}".upper().strip()
    if "OTROS" in nombre or not numero:
        return False
    m = re.match(r"^PL[\s_\-.]*(\d+)", nombre)
    if not m:
        return False
    cifras = m.group(1)
    return cifras.lstrip("0") == str(numero) or (len(cifras) == 13 and int(cifras[:5]) == numero)


def candidatos_proyecto(exp, num_pley):
    """Archivos que pueden tener el texto del proyecto, del mas probable al menos probable."""
    segs = sorted(exp.get("seguimientos") or [], key=lambda s: str(s.get("fecha") or ""))
    todos = [a for s in segs for a in (s.get("archivos") or [])]
    utiles = [a for a in todos if a.get("proyectoArchivoId") and a.get("activo") is not False
              and a.get("publico") is not False]
    sin_oficio = [a for a in utiles if not any(
        x in f"{a.get('nombreArchivo')} {a.get('descripcion')}".lower() for x in ("oficio", "cargo", "decreto de remisi"))]
    m = re.match(r"\s*0*(\d+)", str(num_pley or ""))
    numero = int(m.group(1)) if m else None
    propios = [a for a in utiles if _es_del_proyecto(a, numero)]
    return propios or sin_oficio or utiles


def bajar_archivo(archivo):
    codigo = base64.b64encode(str(archivo["proyectoArchivoId"]).encode()).decode()
    rp = pedir(f"{API_CONGRESO}/archivo/{codigo}/pdf", headers=CABECERAS_CONGRESO)
    if rp.status_code == 404 or rp.content[:4] != b"%PDF":
        return None
    return rp.content


def expediente_proyecto(periodo, camara, num_pley):
    """Devuelve (sumilla, texto, hubo_pdf) del proyecto.
    Revisa hasta 4 archivos posibles y se queda con el de mas texto; si todos son escaneados,
    lee con OCR el mas grande (el proyecto completo)."""
    url = f"{API_CONGRESO}/expediente/{cifrar(periodo)}/{cifrar(num_pley)}"
    r = pedir(url, params={"codTipoParl": camara or "C"}, headers=CABECERAS_CONGRESO)
    if r.status_code == 404:
        return "", "", False
    exp = (r.json() or {}).get("data") or {}
    sumilla = ((exp.get("general") or {}).get("sumilla") or "").strip()
    bajados = []
    for archivo in candidatos_proyecto(exp, num_pley)[:4]:
        datos = bajar_archivo(archivo)
        if datos:
            bajados.append((datos, extraer(datos, ocr=False)))
            if len(bajados[-1][1]) >= 3000:
                break   # ya es el texto del proyecto
    if not bajados:
        return sumilla, "", False
    mejor = max((t for _, t in bajados), key=len)
    if len(mejor) < 3000:
        grande, texto_grande = max(bajados, key=lambda x: len(x[0]))
        if len(texto_grande) < 100:
            leido = ocr_mod.texto_ocr(grande, MAX_CARACTERES)
            if len(leido) > len(mejor):
                mejor = leido
    return sumilla, mejor, True


def extraer(datos, ocr=True) -> str:
    """Texto del PDF. Si es escaneado (casi sin texto) y ocr=True, se lee con OCR."""
    try:
        texto = texto_pdf(datos, MAX_CARACTERES)
    except Exception as e:  # noqa: BLE001  (PDF dañado)
        print(f"    PDF ilegible ({e})")
        texto = ""
    texto = texto.replace("\x00", "").strip()
    if ocr and len(texto) < 100:
        leido = ocr_mod.texto_ocr(datos, MAX_CARACTERES)
        if len(leido) > len(texto):
            texto = leido
    return texto


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


BUSQUEDAS = "https://busquedas.elperuano.pe"


def _story(html) -> str:
    sopa = BeautifulSoup(html, "html.parser")
    for t in sopa(["script", "style"]):
        t.decompose()
    caja = sopa.select_one("div.story")
    if not caja:
        return ""
    texto = re.sub(r"[ \t]+", " ", caja.get_text("\n"))
    return re.sub(r"\n\s*\n+", "\n\n", texto).strip()


def texto_html_norma(url_detalle) -> str:
    """Texto de la norma desde su pagina en El Peruano, cuando el PDF no existe, esta vacio o dañado:
    1) el texto HTML de la pagina (recuadro "story"); 2) el PDF que enlaza esa pagina (otro servidor
    distinto del habitual), leido con OCR si es escaneado."""
    if not url_detalle:
        return ""
    op = codigo_norma(url_detalle)
    paginas = ([f"{BUSQUEDAS}/dispositivo/NL/{op}"] if op else []) + [url_detalle]
    mejor = ""
    for url in paginas:
        r = pedir(url, headers={"User-Agent": AGENTE})
        if r.status_code != 200:
            continue
        texto = _story(r.text)
        if len(texto) > len(mejor):
            mejor = texto
        if len(mejor) >= 200:
            break
        # PDF propio de la pagina (solo si es el de esta norma)
        if op:
            m = re.search(r'(/api/archivo/file/[^"\\]+/' + re.escape(op) + r'\.pdf)', r.text)
            if m:
                rp = pedir(BUSQUEDAS + m.group(1).replace("*", "%2A"), headers={"User-Agent": AGENTE})
                if rp.status_code == 200 and rp.content[:4] == b"%PDF":
                    texto = extraer(rp.content)
                    if len(texto) > len(mejor):
                        mejor = texto
                    if len(mejor) >= 200:
                        break
    return mejor[:MAX_CARACTERES] if len(mejor) >= 100 else ""


_cuadernillos = {}


def texto_cuadernillo(fecha, numero) -> str:
    """Ultimo recurso: las paginas de la edicion completa del dia (cuadernillo de Normas Legales)
    donde aparece el numero de la norma. Se guarda en memoria por fecha (varias normas por dia)."""
    num = re.sub(r"\s+", "", str(numero or ""))
    if len(num) < 5 or not re.search(r"\d", num) or not fecha:
        return ""   # numero demasiado corto: podria confundirse con otras normas
    clave = fecha.strftime("%Y%m%d")
    if clave not in _cuadernillos:
        paginas = []
        r = pedir(f"{BUSQUEDAS}/cuadernillo/NL/{clave}", headers={"User-Agent": AGENTE})
        if r.status_code == 200:
            for ruta in dict.fromkeys(re.findall(r'(/api/archivo/file/[^"\\]+/NL' + clave + r'[^"\\]*\.pdf)', r.text)):
                rp = pedir(BUSQUEDAS + ruta.replace("*", "%2A"), headers={"User-Agent": AGENTE})
                if rp.status_code == 200 and rp.content[:4] == b"%PDF":
                    paginas += _paginas_pdf(rp.content)
        if len(_cuadernillos) > 3:
            _cuadernillos.clear()
        _cuadernillos[clave] = paginas
    paginas = _cuadernillos[clave]
    patron = re.compile(r"\s*".join(re.escape(x) for x in num), re.I)
    elegidas = [i for i, p in enumerate(paginas) if patron.search(p)]
    if len(elegidas) > 1 and elegidas[0] < 6:
        elegidas = elegidas[1:]   # la primera coincidencia suele ser el sumario de la edicion
    return "\n\n".join(paginas[i] for i in elegidas[:3])[:MAX_CARACTERES]


def _paginas_pdf(datos) -> list:
    """Texto de cada pagina (OCR si el PDF es escaneado)."""
    try:
        lector = PdfReader(io.BytesIO(datos))
        salida = []
        for pag in lector.pages:
            try:
                salida.append(pag.extract_text() or "")
            except Exception:  # noqa: BLE001
                salida.append("")
        if sum(len(x) for x in salida) >= 100 * max(1, len(salida)) / 4:
            return salida
    except Exception:  # noqa: BLE001
        pass
    # Escaneado o dañado: OCR pagina por pagina
    return ocr_mod.paginas_ocr(datos, 400, 2400)


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
            texto = extraer(datos) if datos is not None else ""
            if len(texto) < 100:
                # Sin PDF, PDF vacio o dañado: se toma el texto de la pagina de la norma
                try:
                    html = texto_html_norma(url)
                except (requests.RequestException, FuenteNoResponde):
                    html = ""
                if len(html) > len(texto):
                    texto = html
            if len(texto) >= 100:
                bases.guardar("N", clave, "ok", texto)
            else:
                bases.guardar("N", clave, "sin_pdf" if datos is None else "sin_texto", "")
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
        # Avance de una configuracion anterior (otro numero de trabajadores): ya no aplica
        bases.limpiar_avance(de)
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


def trabajar_proyectos(minutos, parte=0, de=1):
    reloj = Reloj(minutos)
    bases = Bases()
    nombre = f"proyectos-{parte}-de-{de}"
    bases.limpiar_avance(de, "proyectos")
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
    # Cada trabajador toma su parte (reparto fijo segun la clave)
    pendientes = [(k, f) for k, f in zip(claves, filas)
                  if k not in hechas and zlib.crc32(k.encode()) % de == parte]
    print(f"Proyectos: {len(filas)} en total, {len(pendientes)} pendientes")
    sumillas = []
    hechos = 0
    errores, espera = 0, 30
    try:
        for clave, (periodo, camara, numero, num_pley, titulo) in pendientes:
            if not reloj.queda():
                break
            try:
                sumilla, texto, hubo_pdf = expediente_proyecto(periodo, camara, num_pley)
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
            if not hubo_pdf:
                bases.guardar("P", clave, "sin_pdf", cabecera)
            else:
                estado = "ok" if len(texto) >= 100 else "sin_texto"
                bases.guardar("P", clave, estado, f"{cabecera}\n\n{texto}".strip())
            sumillas.append((sumilla, periodo, camara, numero))
            hechos += 1
            if hechos % 100 == 0:
                print(f"  {hechos} proyectos procesados")
            time.sleep(PAUSA["proyectos"])
        terminado = hechos >= len(pendientes)
        bases.guardar_avance(nombre, None, terminado, hechos)
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
        trabajar_proyectos(a.max_minutos, a.parte, a.de)


if __name__ == "__main__":
    main()
