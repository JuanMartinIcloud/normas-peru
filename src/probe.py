"""Sondeo de la fuente: descubre como carga El Peruano su listado de normas.

Ejecutar en TU computadora (o en GitHub Actions), no en un entorno con internet restringido:

    python src/probe.py

Guarda el HTML y los scripts en ./probe_out/ y muestra posibles endpoints.
Con eso ajustamos ELPERUANO_ENDPOINT en config.py.
"""
import os
import re
from urllib.parse import urljoin

import requests

BASE = "https://diariooficial.elperuano.pe"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)"}
OUT = "probe_out"

PATRONES = re.compile(
    r"""["'](/?[A-Za-z0-9_/\-\.]*(?:Normas|normas|Obtener|obtener|Listar|listar|GetNormas|api)[A-Za-z0-9_/\-\.\?=&]*)["']"""
)


def main():
    os.makedirs(OUT, exist_ok=True)
    r = requests.get(f"{BASE}/Normas", headers=HEADERS, timeout=30)
    print("HTTP", r.status_code, len(r.text), "bytes")
    with open(f"{OUT}/normas.html", "w", encoding="utf-8") as f:
        f.write(r.text)

    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
    candidatos = set(PATRONES.findall(r.text))

    for s in scripts:
        if "google" in s or "scorecard" in s or "gtm" in s:
            continue
        url = urljoin(BASE + "/", s)
        try:
            js = requests.get(url, headers=HEADERS, timeout=30).text
        except requests.RequestException as e:
            print("No se pudo bajar", url, e)
            continue
        nombre = re.sub(r"[^A-Za-z0-9_.-]", "_", s)[-80:]
        with open(f"{OUT}/{nombre}", "w", encoding="utf-8") as f:
            f.write(js)
        candidatos |= set(PATRONES.findall(js))
        print("Script guardado:", url)

    print("\nPosibles endpoints encontrados:")
    for c in sorted(candidatos):
        print("  ", c)
    print(f"\nRevisa {OUT}/ y busca la llamada AJAX que se dispara al pulsar 'Buscar'.")
    print("Tip: en Chrome, F12 > Network > Fetch/XHR, pulsa Buscar y copia la URL y los parametros.")


if __name__ == "__main__":
    main()


def muestra():
    """Pide al servidor un dia real y guarda la respuesta para ver la estructura."""
    os.makedirs(OUT, exist_ok=True)
    for nombre, desde, hasta in [("muestra_dia.html", "09/10/2026", "09/10/2026"),
                                 ("muestra_hoy.html", "10/10/2026", "10/10/2026")]:
        r = requests.post(
            f"{BASE}/Normas/Filtro",
            data={"cddesde": desde, "cdhasta": hasta},
            headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
            timeout=60,
        )
        print(nombre, "HTTP", r.status_code, len(r.text), "bytes", "| articles:", r.text.count("<article"))
        with open(f"{OUT}/{nombre}", "w", encoding="utf-8") as f:
            f.write(r.text)


if __name__ == "__main__":
    muestra()
