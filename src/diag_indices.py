"""Diagnostico temporal: prueba de las fuentes alternativas de normas."""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from datetime import date
import requests
import indexar
A = {"User-Agent": indexar.AGENTE}
B = indexar.BUSQUEDAS
for ruta in ("/api/archivo/file/B-1pfYYkq5fAD6NRVvVxtT/*/1582046-1.pdf", "/api/archivo/file/B-1pfYYkq5fAD6NRVvVxtT/%2A/1582046-1.pdf"):
    r = requests.get(B + ruta, headers=A, timeout=120); print(ruta[-30:], r.status_code, len(r.content), r.content[:8])
t = time.time()
x = indexar.texto_cuadernillo(date(2017, 11, 1), "0411-2017-JNE"); print("cuadernillo JNE", len(x), round(time.time() - t), repr(x[:700]))
for u in ("https://busquedas.elperuano.pe/dispositivo/NL/2492749-1", "https://busquedas.elperuano.pe/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"):
    x = indexar.texto_html_norma(u); print("html", u[-30:], len(x), repr(x[:200]))
