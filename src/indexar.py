"""Guarda el TEXTO COMPLETO de cada norma (PDF oficial de El Peruano) y de cada proyecto de ley
(PDF del Congreso) para el buscador y la IA. El PDF no se guarda: se lee y se descarta.

    python src/indexar.py normas --parte 0 --de 3      # trabajador 1 de 3 para normas
    python src/indexar.py proyectos                     # proyectos de ley
    python src/indexar.py normas --max-minutos 20

- Empieza por lo mas reciente y se reanuda solo (cada ejecucion sigue con lo pendiente).
- Varios trabajadores pueden correr a la vez: cada uno toma una parte distinta (id % de == parte).
- El texto va a la tabla "textos" de la base principal; cuando esta llega al limite, a las bases
  adicionales del secreto TEXTOS_URLS (cadenas de conexion separadas por coma). En cada documento
  se anota el numero de base: 0 = principal, 1 = primera adicional, etc.
- Si El Peruano o el Congreso responden con errores, espera cada vez mas antes de seguir.
"""
import argparse
import base64
import os
import random
import re
import time

import psycopg2
import requests

import config
import db
from textos import (AGENTE, API_CONGRESO, CABECERAS_CONGRESO, EPDOC, cifrar, texto_pdf)

MAX_CARACTERES = 200_000            # texto que se guarda por documento (los anexos enormes se recortan)
LIMITE_MB = int(os.getenv("TEXTOS_LIMITE_MB", "900"))   # una base gratuita de Neon admite 1 GB
PAUSA = {"normas": 1.5, "proyectos": 1.0}
MAX_ERRORES_SEGUIDOS = 12

SQL_BASE_TEXTOS = """
CREATE TABLE IF NOT EXISTS textos (
    tipo      CHAR(1)     NOT NULL,
    doc_id    BIGINT      NOT NULL,
    texto     TEXT        NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tipo, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_textos_busqueda ON textos USING GIN (to_tsvector('spanish', texto));
"""

_s = requests.Session()


class FuenteNoResponde(Exception):
    pass


# --------------------------------------------------------------------------- bases de texto


class Bases:
    """Conexiones a la base principal (0) y a las adicionales (1, 2, ...)."""

    def __init__(self, principal):
        self.conexiones = [principal]
        for url in [u.strip() for u in os.getenv("TEXTOS_URLS", "").split(",") if u.strip()]:
            c = psycopg2.connect(url)
            with c.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(724502)")
                cur.execute(SQL_BASE_TEXTOS)
            c.commit()
            self.conexiones.append(c)
        self.actual = None
        self.revisado = 0

    def tamano_mb(self, i) -> float:
        with self.conexiones[i].cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database()) / 1048576.0")
            mb = float(cur.fetchone()[0])
        self.conexiones[i].commit()
        return mb

    def destino(self) -> int:
        """Base con espacio libre. Se revisa el tamaño cada 100 documentos."""
        if self.actual is not None and self.revisado < 100:
            self.revisado += 1
            return self.actual
        self.revisado = 0
        for i in range(len(self.conexiones)):
            if self.tamano_mb(i) < LIMITE_MB:
                if i != self.actual:
                    print(f"Guardando textos en la base {i} ({self.tamano_mb(i):.0f} MB usados)")
                self.actual = i
                return i
        raise SystemExit(
            f"::error title=Bases llenas::Todas las bases de texto llegaron a {LIMITE_MB} MB. "
            "Hay que crear otra base gratuita en Neon y agregarla al secreto TEXTOS_URLS."
        )

    def guardar(self, tipo, doc_id, texto) -> int:
        i = self.destino()
        c = self.conexiones[i]
        with c.cursor() as cur:
            cur.execute(
                """INSERT INTO textos (tipo, doc_id, texto) VALUES (%s, %s, %s)
                   ON CONFLICT (tipo, doc_id) DO UPDATE SET texto = EXCLUDED.texto, creado_en = now()""",
                (tipo, doc_id, texto),
            )
        c.commit()
        return i

    def cerrar(self):
        for c in self.conexiones[1:]:
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


def pdf_proyecto(periodo, camara, num_pley):
    url = f"{API_CONGRESO}/expediente/{cifrar(periodo)}/{cifrar(num_pley)}"
    r = pedir(url, params={"codTipoParl": camara or "C"}, headers=CABECERAS_CONGRESO)
    if r.status_code == 404:
        return None
    exp = (r.json() or {}).get("data") or {}
    segs = sorted(exp.get("seguimientos") or [], key=lambda s: str(s.get("fecha") or ""))
    todos = [a for s in segs for a in (s.get("archivos") or [])]
    utiles = [a for a in todos if a.get("proyectoArchivoId") and a.get("activo") is not False
              and a.get("publico") is not False]
    sin_oficio = [a for a in utiles if not any(
        x in f"{a.get('nombreArchivo')} {a.get('descripcion')}".lower() for x in ("oficio", "cargo", "decreto de remisi"))]
    archivo = (sin_oficio or utiles or [None])[0]
    if not archivo:
        return None
    codigo = base64.b64encode(str(archivo["proyectoArchivoId"]).encode()).decode()
    rp = pedir(f"{API_CONGRESO}/archivo/{codigo}/pdf", headers=CABECERAS_CONGRESO)
    if rp.status_code == 404 or rp.content[:4] != b"%PDF":
        return None
    return rp.content


# --------------------------------------------------------------------------- trabajo


def pendientes(conn, tipo, parte, de):
    with conn.cursor() as cur:
        if tipo == "normas":
            cur.execute(
                """SELECT id, fecha, url_detalle FROM normas
                   WHERE texto_estado IS NULL AND url_detalle IS NOT NULL AND id %% %s = %s
                   ORDER BY fecha DESC, id DESC""",
                (de, parte),
            )
        else:
            cur.execute(
                """SELECT id, periodo, camara, num_pley FROM proyectos_ley
                   WHERE texto_estado IS NULL AND num_pley IS NOT NULL AND id %% %s = %s
                   ORDER BY fecha_presentacion DESC NULLS LAST, id DESC""",
                (de, parte),
            )
        filas = cur.fetchall()
    conn.commit()
    return filas


def marcar(conn, tipo, doc_id, estado, base):
    tabla = "normas" if tipo == "normas" else "proyectos_ley"
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {tabla} SET texto_estado = %s, texto_base = %s WHERE id = %s", (estado, base, doc_id))
    conn.commit()


def trabajar(tipo, parte, de, max_minutos):
    hasta = time.time() + max_minutos * 60
    conn = db.conectar()
    bases = Bases(conn)
    lista = pendientes(conn, tipo, parte, de)
    print(f"{tipo} (parte {parte + 1} de {de}): {len(lista)} pendientes")
    hechos = errores = 0
    espera = 30
    letra = "N" if tipo == "normas" else "P"
    time.sleep(random.uniform(0, 5) * parte)   # que los trabajadores no empiecen exactamente a la vez
    try:
        for fila in lista:
            if time.time() >= hasta:
                break
            doc_id = fila[0]
            try:
                datos = pdf_norma(fila[2], fila[1]) if tipo == "normas" else pdf_proyecto(*fila[1:])
                errores, espera = 0, 30
            except (requests.RequestException, FuenteNoResponde, ValueError) as e:
                errores += 1
                print(f"  {letra}{doc_id}: {e}; espero {espera} s")
                if errores >= MAX_ERRORES_SEGUIDOS:
                    print("  La fuente no responde; se continuara en la proxima ejecucion.")
                    break
                time.sleep(espera)
                espera = min(espera * 2, 600)
                continue
            if datos is None:
                marcar(conn, tipo, doc_id, "sin_pdf", None)
            else:
                try:
                    texto = texto_pdf(datos, MAX_CARACTERES)
                except Exception as e:  # noqa: BLE001  (PDF dañado o escaneado sin texto)
                    print(f"  {letra}{doc_id}: PDF ilegible ({e})")
                    texto = ""
                texto = texto.replace("\x00", "").strip()
                if len(texto) < 100:
                    marcar(conn, tipo, doc_id, "sin_texto", None)
                else:
                    base = bases.guardar(letra, doc_id, texto)
                    marcar(conn, tipo, doc_id, "ok", base)
            hechos += 1
            if hechos % 100 == 0:
                print(f"  {hechos} documentos procesados")
            time.sleep(PAUSA[tipo])
    finally:
        print(f"{tipo} parte {parte + 1}: {hechos} documentos procesados en esta ejecucion")
        bases.cerrar()
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tipo", choices=["normas", "proyectos"])
    p.add_argument("--parte", type=int, default=0)
    p.add_argument("--de", type=int, default=1)
    p.add_argument("--max-minutos", type=float, default=50)
    a = p.parse_args()
    if not config.DATABASE_URL:
        raise SystemExit("Falta DATABASE_URL")
    trabajar(a.tipo, a.parte, a.de, a.max_minutos)


if __name__ == "__main__":
    main()
