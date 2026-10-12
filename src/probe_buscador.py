"""Sondeo del buscador de texto completo de busquedas.elperuano.pe: guarda su codigo y rutas de datos."""
import os
import re

import requests

BASE = "https://busquedas.elperuano.pe"
OUT = "sondeo_buscador"
UA = {"User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)"}


def main():
    os.makedirs(OUT, exist_ok=True)
    paginas = {}
    for ruta in ["/", "/dispositivo/NL/2562861-1", "/?s=violencia%20psicologica"]:
        r = requests.get(BASE + ruta, headers=UA, timeout=60)
        print(ruta, r.status_code, len(r.text))
        paginas[ruta] = r.text
    with open(f"{OUT}/inicio.html", "w", encoding="utf-8") as f:
        f.write(paginas["/"])
    scripts = set()
    for html in paginas.values():
        scripts |= set(re.findall(r'(?:src|href)="(/assets/[^"]+\.js)"', html))
    print("scripts:", sorted(scripts))
    rutas = set()
    for s in sorted(scripts):
        js = requests.get(BASE + s, headers=UA, timeout=60).text
        nombre = s.split("/")[-1]
        with open(f"{OUT}/{nombre}", "w", encoding="utf-8") as f:
            f.write(js)
        for m in re.findall(r'["`\'](/?(?:api|Api|API)[^"`\']{0,120}|https?://[^"`\' ]{4,150})["`\']', js):
            rutas.add(m)
        # importaciones dinamicas de otros trozos de codigo
        for m in re.findall(r'"\./([A-Za-z0-9_.-]+\.js)"', js):
            sub = requests.get(f"{BASE}/assets/{m}", headers=UA, timeout=60)
            if sub.ok:
                with open(f"{OUT}/{m}", "w", encoding="utf-8") as f:
                    f.write(sub.text)
                for mm in re.findall(r'["`\'](/?(?:api|Api|API)[^"`\']{0,120}|https?://[^"`\' ]{4,150})["`\']', sub.text):
                    rutas.add(mm)
    with open(f"{OUT}/rutas.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(rutas)))
    print(len(rutas), "rutas encontradas")


if __name__ == "__main__":
    main()
