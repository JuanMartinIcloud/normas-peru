"""Diagnostico temporal: texto HTML (div.story) en normas sin PDF y enlace del cuadernillo."""
import os, sys, re, random
sys.path.insert(0, os.path.dirname(__file__))
import requests
from bs4 import BeautifulSoup
from indexar import Bases, principal
from textos import AGENTE
b = Bases()
sinpdf = []
for u in b.urls:
    sinpdf += b.ejecutar(u, lambda cur: (cur.execute("SELECT clave FROM documentos WHERE tipo='N' AND estado='sin_pdf'"), [r[0] for r in cur.fetchall()])[1])
print("sin_pdf:", len(sinpdf))
c = principal(); cur = c.cursor()
cur.execute("SELECT hash_unico, fecha, url_detalle FROM normas WHERE hash_unico = ANY(%s)", (sinpdf,))
filas = cur.fetchall()
por = {}
for _, f, _ in filas: por[f.year] = por.get(f.year, 0) + 1
print("por anio:", sorted(por.items()))
print("sin url:", sum(1 for x in filas if not x[2]))
random.seed(3)
ok = 0
for k, f, url in random.sample([x for x in filas if x[2]], 25):
    try:
        r = requests.get(url, headers={"User-Agent": AGENTE}, timeout=60)
        s = BeautifulSoup(r.text, "html.parser")
        st = s.select_one("div.story")
        t = re.sub(r"\s+", " ", st.get_text(" ")).strip() if st else ""
        ok += len(t) >= 200
        print(f, r.status_code, len(t), url[:90], "|", t[:120])
    except Exception as e:
        print(f, "error", e)
print("con texto HTML:", ok, "de 25")
u2 = "https://busquedas.elperuano.pe/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"
s2 = BeautifulSoup(requests.get(u2, headers={"User-Agent": AGENTE}, timeout=60).text, "html.parser")
for a in s2.find_all(["a", "button"]):
    if "uadernillo" in a.get_text() or "PDF" in a.get_text():
        print("ENLACE", a.get_text(strip=True), a.attrs)
