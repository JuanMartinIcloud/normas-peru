"""Diagnostico temporal: estructura HTML de la norma y reparacion del PDF dañado."""
import os, sys, re, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import requests
from bs4 import BeautifulSoup
from indexar import pdf_norma
from textos import AGENTE
from datetime import date
import ocr
url = "https://busquedas.elperuano.pe/dispositivo/NL/2492749-1"
s = BeautifulSoup(requests.get(url, headers={"User-Agent": AGENTE}, timeout=60).text, "html.parser")
for t in s(["script", "style"]): t.decompose()
cands = [e for e in s.find_all(True) if "CONSIDERANDO" in e.get_text()]
for e in cands[-6:]:
    print(e.name, e.get("id"), e.get("class"), len(e.get_text()))
print("---")
e = cands[-1]
print(repr(re.sub(r"\s+", " ", e.get_text(" "))[:400]))
# pdf dañado
u2 = "https://busquedas.elperuano.pe/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"
d = pdf_norma(u2, date(2017, 11, 1))
print("\nPDF", len(d), d[:300])
print(d[-400:])
with tempfile.TemporaryDirectory() as t:
    open(f"{t}/a.pdf", "wb").write(d)
    for cmd in (["gs", "-q", "-o", f"{t}/g.pdf", "-sDEVICE=pdfwrite", f"{t}/a.pdf"], ["mutool", "clean", f"{t}/a.pdf", f"{t}/m.pdf"]):
        r = subprocess.run(cmd, capture_output=True, text=True); print(cmd[0], r.returncode, r.stderr[:300])
    for f in ("g.pdf", "m.pdf"):
        if os.path.exists(f"{t}/{f}"):
            dd = open(f"{t}/{f}", "rb").read()
            print(f, len(dd), "pdftotext", len(subprocess.run(["pdftotext", f"{t}/{f}", "-"], capture_output=True).stdout), "ocr", len(ocr.texto_ocr(dd)))
s2 = BeautifulSoup(requests.get(u2, headers={"User-Agent": AGENTE}, timeout=60).text, "html.parser")
print([ (x.name, x.get("src") or x.get("data-src") or x.get("href")) for x in s2.find_all(["iframe", "embed", "object", "a"]) if "pdf" in str(x).lower()][:10])
