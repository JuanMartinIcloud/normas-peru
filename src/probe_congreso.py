"""Sondeo del Congreso: busca de donde carga sus datos el portal de proposiciones legislativas.

Se ejecuta en GitHub Actions (flujo 'Sondeo del Congreso'). Guarda todo en ./sondeo_congreso/
"""
import os
import re
from urllib.parse import urljoin

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)"}
OUT = "sondeo_congreso"

PAGINAS = [
    "https://wb2server.congreso.gob.pe/spley-portal/",
    "https://www.congreso.gob.pe/pley-2021-2026",
    "https://www2.congreso.gob.pe/Sicr/TraDocEstProc/CLProLey2021.nsf/Local%20Por%20Numero?OpenView",
    "https://leyes.congreso.gob.pe/",
]

PATRON_API = re.compile(
    r"""["'`]((?:https?:)?//[^"'`\s]*congreso[^"'`\s]*|/?[A-Za-z0-9_\-/]*(?:service|api|proyecto|proposicion|ley)[A-Za-z0-9_\-/\.\?=&{}$]*)["'`]""",
    re.I,
)


def guardar(nombre, texto):
    seguro = re.sub(r"[^A-Za-z0-9_.-]", "_", nombre)[-120:]
    with open(f"{OUT}/{seguro}", "w", encoding="utf-8") as f:
        f.write(texto)


def main():
    os.makedirs(OUT, exist_ok=True)
    resumen = []
    for url in PAGINAS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=40, allow_redirects=True)
        except requests.RequestException as e:
            resumen.append(f"{url} -> ERROR {e}")
            continue
        resumen.append(f"{url} -> HTTP {r.status_code}, {len(r.text)} bytes, final: {r.url}")
        guardar("pagina_" + url, r.text)

        scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
        for s in scripts:
            if any(x in s for x in ("google", "gtm", "facebook")):
                continue
            js_url = urljoin(r.url, s)
            try:
                js = requests.get(js_url, headers=HEADERS, timeout=60).text
            except requests.RequestException as e:
                resumen.append(f"   script {js_url} ERROR {e}")
                continue
            guardar("js_" + js_url, js)
            hallazgos = sorted(set(PATRON_API.findall(js)))[:60]
            resumen.append(f"   script {js_url}: {len(js)} bytes, {len(hallazgos)} posibles rutas")
            for h in hallazgos:
                resumen.append(f"      {h}")

    texto = "\n".join(resumen)
    print(texto)
    guardar("RESUMEN.txt", texto)


if __name__ == "__main__":
    main()
