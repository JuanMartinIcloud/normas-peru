"""Funciones comunes para leer documentos oficiales: PDF de El Peruano y portal del Congreso.

Las usan src/indexar.py (texto completo), src/monitoreo.py (analisis) y src/seguimiento.py.
"""
import base64
import io
import logging
import re

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pypdf import PdfReader

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
MAX_TEXTO = 60_000           # caracteres por documento que se leen para el analisis

_s = requests.Session()


def cifrar(texto: str) -> str:
    rel = padding.PKCS7(128).padder()
    datos = rel.update(str(texto).encode()) + rel.finalize()
    enc = Cipher(algorithms.AES(CLAVE_PORTAL), modes.ECB()).encryptor()
    salida = enc.update(datos) + enc.finalize()
    return base64.b64encode(salida).decode().replace("+", "-").replace("/", "_").replace("=", "")


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
