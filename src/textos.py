"""Guarda la sumilla extensa de cada proyecto de ley (expediente del Congreso).

El texto completo de normas y proyectos lo guarda src/indexar.py; este archivo tambien
reune funciones que ese programa usa (lectura de PDF, cifrado del portal del Congreso).

    python src/textos.py                       # hasta 50 minutos de trabajo

Se reanuda solo: cada ejecucion continua con lo que falta. Respeta una pausa entre
pedidos para no cargar los servidores del Estado.
"""
import argparse
import base64
import io
import logging
import re
import time

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pypdf import PdfReader

import db

logging.getLogger("pypdf").setLevel(logging.ERROR)   # avisos menores de PDFs mal formados

AGENTE = "Mozilla/5.0 (compatible; normas-peru/0.2; consulta de documentos publicos)"
API_CONGRESO = "https://api.congreso.gob.pe/spley-portal-service"
CLAVE_PORTAL = b"ProdALg5ZrAsxBMD"   # clave publica que usa el propio portal del Congreso en el navegador
CABECERAS_CONGRESO = {
    "User-Agent": AGENTE,
    "Origin": "https://wb2server.congreso.gob.pe",
    "Referer": "https://wb2server.congreso.gob.pe/",
    "Accept": "application/json, text/plain, */*",
}
EPDOC = "https://epdoc2.elperuano.pe/EpPo/VistaDE.asp"
PAUSA_CONGRESO = 0.5
PAUSA_PERUANO = 1.5
MAX_TEXTO = 60_000           # caracteres por norma que se leen (los anexos largos se omiten)
MAX_PALABRAS = 200           # palabras distintas que se guardan por norma (las mas repetidas)
MAX_ERRORES_SEGUIDOS = 15    # si la fuente falla tanto, se deja para la proxima ejecucion

_s = requests.Session()


def cifrar(texto: str) -> str:
    rel = padding.PKCS7(128).padder()
    datos = rel.update(str(texto).encode()) + rel.finalize()
    enc = Cipher(algorithms.AES(CLAVE_PORTAL), modes.ECB()).encryptor()
    salida = enc.update(datos) + enc.finalize()
    return base64.b64encode(salida).decode().replace("+", "-").replace("/", "_").replace("=", "")


# --------------------------------------------------------------------------- proyectos


def sumilla_proyecto(periodo, camara, num_pley) -> str:
    url = f"{API_CONGRESO}/expediente/{cifrar(periodo)}/{cifrar(num_pley)}"
    r = _s.get(url, params={"codTipoParl": camara or "C"}, headers=CABECERAS_CONGRESO, timeout=60)
    r.raise_for_status()
    general = ((r.json() or {}).get("data") or {}).get("general") or {}
    return (general.get("sumilla") or "").strip()


def cargar_sumillas(conn, hasta: float) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, periodo, camara, num_pley FROM proyectos_ley
               WHERE NOT sumilla_revisada AND num_pley IS NOT NULL
               ORDER BY fecha_presentacion DESC NULLS LAST, id DESC"""
        )
        pendientes = cur.fetchall()
    print(f"Proyectos sin sumilla extensa: {len(pendientes)}")
    hechos = errores = 0
    for pid, periodo, camara, num in pendientes:
        if time.time() >= hasta:
            break
        try:
            sumilla = sumilla_proyecto(periodo, camara, num)
            errores = 0
        except (requests.RequestException, ValueError) as e:
            errores += 1
            print(f"  proyecto {pid}: {e}")
            if errores >= MAX_ERRORES_SEGUIDOS:
                print("  El Congreso no responde; se continuara en la proxima ejecucion.")
                break
            time.sleep(5)
            continue
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE proyectos_ley SET sumilla = NULLIF(%s, ''), sumilla_revisada = TRUE WHERE id = %s",
                (sumilla, pid),
            )
        conn.commit()
        hechos += 1
        if hechos % 200 == 0:
            print(f"  {hechos} sumillas guardadas")
        time.sleep(PAUSA_CONGRESO)
    print(f"Sumillas guardadas en esta ejecucion: {hechos}")
    return hechos


# --------------------------------------------------------------------------- normas


def texto_pdf(datos: bytes, maximo: int = MAX_TEXTO) -> str:
    lector = PdfReader(io.BytesIO(datos))
    partes = []
    total = 0
    for pagina in lector.pages:
        try:
            t = pagina.extract_text() or ""
        except Exception:  # noqa: BLE001  (una pagina dañada no debe frenar el resto)
            t = ""
        partes.append(t)
        total += len(t)
        if total >= maximo:
            break
    texto = "\n".join(partes)
    texto = re.sub(r"-\n(?=[a-záéíóúñ])", "", texto)   # une palabras cortadas al final de linea
    return re.sub(r"[ \t]+", " ", texto)[:maximo]


def codigo_norma(url_detalle: str) -> str | None:
    """Codigo de la norma en El Peruano (ej. "2562861-1") a partir de su enlace. Formatos conocidos:
    .../dispositivo/NL/2562861-1                      (2023 en adelante)
    .../normaslegales/<titulo>-1849787-2/             (2016-2023)
    .../NormasElperuano/2015/02/14/1200944-7.html     (2015 y algunas posteriores)
    .../NormasElperuano/2021/03/17/1935627-1/1935627-1.htm
    epdoc2.../VistaDE.asp o DescargaIN.asp?Referencias=<base64 de codigo+AAAAMMDD>"""
    u = (url_detalle or "").strip()
    m = re.search(r"/dispositivo/[A-Z]+/(\d+-\d+)", u)
    if m:
        return m.group(1)
    m = re.search(r"Referencias=([A-Za-z0-9+/=_-]+)", u)
    if m:
        try:
            dec = base64.b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4)).decode()
            m2 = re.fullmatch(r"(\d+)[-_](\d{1,3}?)(\d{8})", dec)  # "2442245-1"+fecha o "1602563_1"+fecha
            if m2:
                return f"{m2.group(1)}-{m2.group(2)}"
        except Exception:  # noqa: BLE001
            pass
    m = re.search(r"(\d{5,}-\d+)(?:-\d+)?(?:\.html?)?/?$", u)
    return m.group(1) if m else None


def pdf_norma(url_detalle: str, fecha) -> bytes | None:
    codigo = codigo_norma(url_detalle)
    if not codigo:
        return None
    ref = base64.b64encode(f"{codigo}{fecha.strftime('%Y%m%d')}".encode()).decode()
    r = _s.get(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE}, timeout=90)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content if r.content[:4] == b"%PDF" else None


def cargar_textos(conn, dias: int, hasta: float) -> int:
    with conn.cursor() as cur:
        # Normas guardadas con mas palabras que el limite actual: se vuelven a procesar
        cur.execute(
            """UPDATE normas SET texto_estado = NULL, texto_tsv = NULL
               WHERE texto_tsv IS NOT NULL AND length(texto_tsv) > %s""",
            (MAX_PALABRAS,),
        )
        if cur.rowcount:
            print(f"{cur.rowcount} normas se volveran a procesar con el limite de {MAX_PALABRAS} palabras")
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, fecha, url_detalle FROM normas
               WHERE texto_estado IS NULL AND url_detalle IS NOT NULL
                 AND fecha >= (now() AT TIME ZONE 'America/Lima')::date - %s
               ORDER BY fecha DESC, id DESC""",
            (dias,),
        )
        pendientes = cur.fetchall()
    print(f"Normas de los ultimos {dias} dias sin texto completo: {len(pendientes)}")
    hechos = errores = 0
    for nid, fecha, url in pendientes:
        if time.time() >= hasta:
            break
        try:
            datos = pdf_norma(url, fecha)
            errores = 0
        except requests.RequestException as e:
            errores += 1
            print(f"  norma {nid}: {e}")
            if errores >= MAX_ERRORES_SEGUIDOS:
                print("  El Peruano no responde; se continuara en la proxima ejecucion.")
                break
            time.sleep(10)
            continue
        if datos is None:
            estado, texto = "sin_pdf", ""
        else:
            try:
                texto = texto_pdf(datos)
            except Exception as e:  # noqa: BLE001  (PDF ilegible)
                print(f"  norma {nid}: PDF ilegible ({e})")
                texto = ""
            estado = "ok" if len(texto.strip()) >= 200 else "sin_texto"
        with conn.cursor() as cur:
            # Solo se guardan las palabras mas repetidas de la norma: bastan para encontrarla
            # por su tema y ocupan una fraccion del espacio (la base gratuita es pequeña)
            cur.execute(
                """UPDATE normas SET texto_estado = %(estado)s,
                          texto_tsv = (SELECT array_to_tsvector(array_agg(lexeme))
                                       FROM (SELECT lexeme FROM unnest(to_tsvector('spanish', %(texto)s))
                                             WHERE length(lexeme) > 2
                                             ORDER BY coalesce(array_length(positions, 1), 0) DESC, lexeme
                                             LIMIT %(max)s) t)
                   WHERE id = %(id)s""",
                {"estado": estado, "texto": texto, "max": MAX_PALABRAS, "id": nid},
            )
        conn.commit()
        hechos += 1
        if hechos % 100 == 0:
            print(f"  {hechos} normas procesadas")
        time.sleep(PAUSA_PERUANO)
    print(f"Normas procesadas en esta ejecucion: {hechos}")
    return hechos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--dias", type=int, default=60, help="(ya no se usa; se conserva por compatibilidad)")
    a = p.parse_args()
    hasta = time.time() + a.max_minutos * 60

    conn = db.conectar()
    try:
        # El texto completo de las normas ahora lo guarda src/indexar.py
        cargar_sumillas(conn, hasta)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
