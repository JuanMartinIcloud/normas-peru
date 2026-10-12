"""Sondeo: que direcciones de El Peruano responden y con que tipo de contenido."""
import os

import requests

OUT = "sondeo_buscador"
UA = {"User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)"}
URLS = [
    "https://busquedas.elperuano.pe/dispositivo/NL/2562861-1",
    "https://busquedas.elperuano.pe/dispositivo/NL/2562861-1/pdf",
    "https://busquedas.elperuano.pe/cuadernillo/NL/20261009",
    "https://epdoc2.elperuano.pe/EpPo/VistaDE.asp?Referencias=MjU2MjcxMS0xMjAyNjEwMDk=",
    "https://diariooficial.elperuano.pe/Normas",
    "https://busquedas.elperuano.pe/",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, u in enumerate(URLS):
        try:
            r = requests.get(u, headers=UA, timeout=60)
            print(u, "->", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:60])
            with open(f"{OUT}/respuesta_{i}.bin", "wb") as f:
                f.write(r.content[:300000])
        except requests.RequestException as e:
            print(u, "-> ERROR", e)


if __name__ == "__main__":
    main()
