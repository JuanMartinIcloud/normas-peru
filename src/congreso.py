"""Cliente del portal de proposiciones legislativas del Congreso (proyectos de ley)."""
import time

import requests

from classifier import clasificar_rubro

API = "https://api.congreso.gob.pe/spley-portal-service"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1; uso academico)",
    "Origin": "https://wb2server.congreso.gob.pe",
    "Referer": "https://wb2server.congreso.gob.pe/",
    "Accept": "application/json, text/plain, */*",
}
PAGINA = 200          # el portal ofrece 20, 50, 100 o 200
PAUSA = 1.0           # segundos entre solicitudes
CAMARAS = ["C", "D", "S"]   # Congreso, Diputados, Senado (este ultimo desde 2026)

_s = requests.Session()
_s.headers.update(HEADERS)


def _con_reintentos(fn, *a, **kw):
    ultimo = None
    for intento in range(1, 5):
        try:
            r = fn(*a, timeout=90, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            ultimo = e
            time.sleep(min(60, 3 * 2 ** intento))
    raise RuntimeError(f"Fallo tras 4 intentos: {ultimo}")


def periodos() -> list[dict]:
    return _con_reintentos(_s.get, f"{API}/periodo-parlamentario")["data"]


def _cuerpo(per_id, camara, inicio):
    return {
        "perParId": per_id, "codTipoParl": camara, "perLegId": None, "comisionId": None,
        "estadoId": None, "congresistaId": None, "grupoParlamentarioId": None,
        "proponenteId": None, "legislaturaId": None, "fecPresentacionDesde": None,
        "fecPresentacionHasta": None, "pleyNum": None, "palabras": None,
        "tipoFirmanteId": None, "conAcumulado": None, "pageSize": PAGINA, "rowStart": inicio,
    }


def paginas(per_id: int, camara: str):
    """Genera listas de proyectos (de a 200) de un periodo y camara. Termina solo."""
    inicio = 0
    while True:
        datos = _con_reintentos(_s.post, f"{API}/proyecto-ley/lista-con-filtro",
                                json=_cuerpo(per_id, camara, inicio))["data"]
        lote = datos.get("proyectos") or []
        total = datos.get("rowsTotal") or 0
        if lote:
            yield lote, total
        inicio += PAGINA
        time.sleep(PAUSA)
        if not lote or inicio >= total:
            return


def normalizar(p: dict, camara: str) -> dict:
    titulo = (p.get("titulo") or "").strip()
    fecha = (p.get("fecPresentacion") or "")[:10] or None
    numero = p.get("proyectoLey") or str(p.get("pleyNum"))
    return {
        "periodo": str(p.get("perParId")),
        "camara": p.get("codTipoParl") or camara,
        "numero": numero,
        "num_pley": p.get("pleyNum"),
        "fecha_presentacion": fecha,
        "titulo": titulo,
        "autor": p.get("autores"),
        "proponente": p.get("desProponente"),
        "estado": p.get("desEstado"),
        "rubro": clasificar_rubro(titulo),
        "url": None,
    }
