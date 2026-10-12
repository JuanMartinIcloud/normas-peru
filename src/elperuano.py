"""Cliente de El Peruano: descarga y normaliza las normas legales de un rango de fechas."""
import hashlib
import json
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

import config
from classifier import clasificar

_sesion = requests.Session()
_sesion.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json, text/html, */*"})


def _pedir(desde: date, hasta: date) -> requests.Response:
    params = {
        config.PARAM_DESDE: desde.strftime(config.FORMATO_FECHA),
        config.PARAM_HASTA: hasta.strftime(config.FORMATO_FECHA),
    }
    ultimo_error = None
    for intento in range(1, config.REINTENTOS + 1):
        try:
            if config.METODO == "GET":
                r = _sesion.get(config.ENDPOINT, params=params, timeout=config.TIMEOUT)
            else:
                r = _sesion.post(config.ENDPOINT, data=params, timeout=config.TIMEOUT)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            ultimo_error = e
            time.sleep(min(60, config.PAUSA_SEGUNDOS * (2 ** intento)))
    raise RuntimeError(f"Fallo tras {config.REINTENTOS} intentos: {ultimo_error}")


def _campo(item: dict, clave: str):
    for nombre in config.CAMPOS[clave]:
        if nombre in item and item[nombre] not in (None, ""):
            return item[nombre]
    return None


def _desde_json(datos, fecha: date) -> list[dict]:
    if isinstance(datos, dict):
        for k in ("data", "Data", "normas", "Normas", "result", "items"):
            if isinstance(datos.get(k), list):
                datos = datos[k]
                break
        else:
            datos = []
    filas = []
    for it in datos:
        if not isinstance(it, dict):
            continue
        filas.append({
            "tipo": _campo(it, "tipo"),
            "numero": _campo(it, "numero"),
            "entidad": _campo(it, "entidad"),
            "sumilla": _campo(it, "sumilla"),
            "url_pdf": _campo(it, "url_pdf"),
            "extraordinaria": bool(_campo(it, "extraordinaria")),
        })
    return filas


def _desde_html(html: str) -> list[dict]:
    """Respaldo si el endpoint devuelve HTML en vez de JSON (selectores a ajustar tras el sondeo)."""
    soup = BeautifulSoup(html, "html.parser")
    filas = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" not in href.lower():
            continue
        contenedor = a.find_parent(["li", "tr", "div"]) or a
        filas.append({
            "tipo": None,
            "numero": a.get_text(strip=True) or None,
            "entidad": None,
            "sumilla": contenedor.get_text(" ", strip=True),
            "url_pdf": href if href.startswith("http") else config.BASE_URL + "/" + href.lstrip("/"),
            "extraordinaria": False,
        })
    return filas


def _hash(fecha: date, f: dict) -> str:
    base = "|".join([
        fecha.isoformat(), str(f.get("tipo")), str(f.get("numero")),
        str(f.get("entidad")), (f.get("sumilla") or "")[:200], str(f.get("url_pdf")),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def descargar_dia(fecha: date) -> list[dict]:
    """Devuelve las normas de un dia, ya clasificadas y listas para insertar."""
    r = _pedir(fecha, fecha)
    time.sleep(config.PAUSA_SEGUNDOS)
    try:
        filas = _desde_json(r.json(), fecha)
    except (json.JSONDecodeError, ValueError):
        filas = _desde_html(r.text)

    resultado = []
    for f in filas:
        c = clasificar(f.get("entidad") or "", f.get("sumilla") or "", f.get("tipo") or "")
        resultado.append({
            "fecha": fecha,
            "tipo": f.get("tipo"),
            "numero": f.get("numero"),
            "entidad": f.get("entidad"),
            "sector": c["sector"],
            "rubro": c["rubro"],
            "sumilla": f.get("sumilla"),
            "url_pdf": f.get("url_pdf"),
            "extraordinaria": f.get("extraordinaria", False),
            "hash_unico": _hash(fecha, f),
        })
    return resultado
