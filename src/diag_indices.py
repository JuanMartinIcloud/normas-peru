"""Diagnostico temporal: como arma El Peruano el enlace del cuadernillo."""
import re, requests
from bs4 import BeautifulSoup
A = {"User-Agent": "Mozilla/5.0"}
u = "https://busquedas.elperuano.pe/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"
h = requests.get(u, headers=A, timeout=60).text
for m in re.finditer(r"(?i)cuadernillo", h):
    print("HTML:", h[max(0, m.start() - 300): m.start() + 300].replace("\n", " "))
    break
for m in re.finditer(r'(?i)(https?://[^"\'\s<>]*(?:pdf|cuadern|epdoc|download)[^"\'\s<>]*)', h):
    print("URL:", m.group(1)[:200])
srcs = re.findall(r'src="([^"]+\.js[^"]*)"', h)
print(len(srcs), "scripts")
for s in srcs:
    url = s if s.startswith("http") else "https://busquedas.elperuano.pe" + s
    try:
        js = requests.get(url, headers=A, timeout=60).text
    except Exception as e:
        continue
    for m in re.finditer(r"(?i)cuadernillo", js):
        print("JS", s[-60:], ":", js[max(0, m.start() - 400): m.start() + 400].replace("\n", " "))
    for m in re.finditer(r"(?i)(epdoc|DescargaIN|VistaDE|/pdf/|\.pdf)", js):
        print("JSURL", s[-40:], ":", js[max(0, m.start() - 200): m.start() + 200].replace("\n", " "))
# datos embebidos (Next.js)
for m in re.finditer(r'(?i)"(edicion|fecha_?publicacion|codigo|cuadernillo|pdf)[^"]*"\s*:\s*"[^"]{0,200}"', h):
    print("DATA", m.group(0)[:250])
