"""Sondeo: como obtener el texto completo (PDF) de una norma de El Peruano y de un proyecto de ley.

Guarda lo encontrado en sondeo_documentos/ para revisarlo. No escribe en la base.
"""
import base64
import json
import os

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

API = "https://api.congreso.gob.pe/spley-portal-service"
CLAVE_PORTAL = b"ProdALg5ZrAsxBMD"   # clave publica que usa el propio portal del Congreso en el navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; normas-peru-research/0.1)",
    "Origin": "https://wb2server.congreso.gob.pe",
    "Referer": "https://wb2server.congreso.gob.pe/",
    "Accept": "application/json, text/plain, */*",
}
OUT = "sondeo_documentos"


def cifrar(texto: str) -> str:
    rel = padding.PKCS7(128).padder()
    datos = rel.update(texto.encode()) + rel.finalize()
    enc = Cipher(algorithms.AES(CLAVE_PORTAL), modes.ECB()).encryptor()
    salida = enc.update(datos) + enc.finalize()
    return base64.b64encode(salida).decode().replace("+", "-").replace("/", "_").replace("=", "")


def describir(nombre, r):
    info = {"url": r.url, "status": r.status_code, "tipo": r.headers.get("content-type"),
            "bytes": len(r.content), "inicio": r.content[:8].decode("latin-1")}
    print(nombre, info)
    return info


def main():
    os.makedirs(OUT, exist_ok=True)
    resumen = {}
    for periodo, num, camara in [("2026", "6", "C"), ("2021", "2", "C")]:
        url = f"{API}/expediente/{cifrar(periodo)}/{cifrar(num)}"
        r = requests.get(url, params={"codTipoParl": camara}, headers=HEADERS, timeout=60)
        resumen[f"expediente_{periodo}_{num}"] = describir("expediente", r)
        try:
            datos = r.json()
        except ValueError:
            print(r.text[:500])
            continue
        with open(f"{OUT}/expediente_{periodo}_{num}.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        d = datos.get("data") or {}
        archivos = d.get("archivos") or []
        print("claves de data:", list(d.keys()), "| archivos:", len(archivos))
        if archivos:
            a = archivos[0]
            print("primer archivo:", a)
            pid = a.get("proyectoArchivoId")
            if pid:
                cod = base64.b64encode(str(pid).encode()).decode()
                rp = requests.get(f"{API}/archivo/{cod}/pdf", headers=HEADERS, timeout=90)
                resumen[f"pdf_proyecto_{periodo}_{num}"] = describir("pdf proyecto", rp)

    for url in ["https://busquedas.elperuano.pe/dispositivo/NL/2562861-1/pdf",
                "https://busquedas.elperuano.pe/dispositivo/NL/2562861-1"]:
        r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=90)
        resumen[url] = describir("el peruano", r)
        if "html" in (r.headers.get("content-type") or ""):
            with open(f"{OUT}/elperuano_detalle.html", "w", encoding="utf-8") as f:
                f.write(r.text[:200000])
    with open(f"{OUT}/resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
