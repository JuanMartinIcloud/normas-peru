"""Sondeo: que direcciones de El Peruano responden y con que tipo de contenido."""
import os

import requests

OUT = "sondeo_buscador"
UA = {"User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)"}
URLS = [
    "https://epdoc2.elperuano.pe/EpPo/VistaDE.asp?Referencias=MjU2Mjg2MS0xMjAyNjEwMDk=",
    "https://epdoc2.elperuano.pe/EpPo/VistaDE.asp?Referencias=MjU2Mjg2Mi0xMjAyNjEwMDk=",
    "https://epdoc2.elperuano.pe/EpPo/VistaDE.asp?Referencias=MjU2MzE5OS0xMjAyNjEwMDk=",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, u in enumerate(URLS):
        try:
            r = requests.get(u, headers=UA, timeout=90)
            print(u, "->", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:60])
            with open(f"{OUT}/respuesta_{i}.bin", "wb") as f:
                f.write(r.content[:300000])
        except requests.RequestException as e:
            print(u, "-> ERROR", e)


if __name__ == "__main__":
    main()
