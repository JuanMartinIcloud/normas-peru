"""Prueba real contra la interfaz de datos del Congreso: guarda una muestra en sondeo_congreso/."""
import json
import os

import requests

API = "https://api.congreso.gob.pe/spley-portal-service"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)",
    "Origin": "https://wb2server.congreso.gob.pe",
    "Referer": "https://wb2server.congreso.gob.pe/",
    "Accept": "application/json, text/plain, */*",
}
OUT = "sondeo_congreso"


def guardar(nombre, obj):
    with open(f"{OUT}/{nombre}", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    r = requests.get(f"{API}/periodo-parlamentario", headers=HEADERS, timeout=60)
    print("periodos: HTTP", r.status_code, len(r.text), "bytes")
    try:
        periodos = r.json()
    except ValueError:
        print("respuesta no es JSON:", r.text[:300])
        return
    guardar("api_periodos.json", periodos)
    lista = periodos.get("data", periodos) if isinstance(periodos, dict) else periodos
    print("cantidad de periodos:", len(lista))
    for p in lista[:20]:
        print("  ", {k: p.get(k) for k in ("perParId", "desPerParAbrev")})

    # Muestra: 5 proyectos del periodo mas reciente, y 5 del segundo
    for idx, nombre in [(0, "api_proyectos_periodo0.json"), (1, "api_proyectos_periodo1.json")]:
        if idx >= len(lista):
            continue
        per = lista[idx]["perParId"]
        cuerpo = {
            "perParId": per, "codTipoParl": "C", "perLegId": None, "comisionId": None,
            "estadoId": None, "congresistaId": None, "grupoParlamentarioId": None,
            "proponenteId": None, "legislaturaId": None, "fecPresentacionDesde": None,
            "fecPresentacionHasta": None, "pleyNum": None, "palabras": None,
            "tipoFirmanteId": None, "conAcumulado": None, "pageSize": 5, "rowStart": 0,
        }
        rr = requests.post(f"{API}/proyecto-ley/lista-con-filtro", json=cuerpo, headers=HEADERS, timeout=60)
        print(f"proyectos periodo {per}: HTTP {rr.status_code}, {len(rr.text)} bytes")
        try:
            datos = rr.json()
        except ValueError:
            print("   no es JSON:", rr.text[:300])
            continue
        guardar(nombre, datos)
        d = datos.get("data", datos) if isinstance(datos, dict) else datos
        if isinstance(d, dict):
            print("   rowsTotal:", d.get("rowsTotal"), "| proyectos devueltos:", len(d.get("proyectos") or []))


if __name__ == "__main__":
    main()
