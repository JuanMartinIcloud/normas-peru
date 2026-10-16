"""Diagnostico temporal: fuentes alternativas para las 5 normas sin texto."""
import os, sys, re, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import requests
from bs4 import BeautifulSoup
from indexar import Bases, principal, pdf_norma
from textos import AGENTE
import ocr
b = Bases()
claves = b.ejecutar(b.control, lambda cur: (cur.execute("SELECT clave FROM ocr_revisado WHERE tipo='N' AND resultado='sin_texto'"), [r[0] for r in cur.fetchall()])[1])
c = principal(); cur = c.cursor()
cur.execute("SELECT hash_unico, fecha, numero, url_detalle FROM normas WHERE hash_unico = ANY(%s)", (claves,))
for k, fecha, num, url in cur.fetchall():
    print(f"\n== {fecha} {num}\n  {url}")
    try:
        r = requests.get(url, headers={"User-Agent": AGENTE}, timeout=60)
        s = BeautifulSoup(r.text, "html.parser")
        for t in s(["script", "style", "nav", "header", "footer"]): t.decompose()
        txt = re.sub(r"\s+", " ", s.get_text(" "))
        print("  HTML", r.status_code, len(r.text), "texto", len(txt))
        i = txt.find("CONSIDERANDO"); i = i if i >= 0 else txt.find("Considerando")
        print("  ", txt[max(0, i - 200): i + 600] if i >= 0 else txt[:900])
        enl = [a.get("href") for a in s.find_all("a") if a.get("href") and ("pdf" in a.get("href").lower() or "Descarga" in a.get("href"))]
        print("  enlaces pdf:", enl[:6])
    except Exception as e:
        print("  HTML error", e)
    d = pdf_norma(url, fecha)
    if d:
        with tempfile.TemporaryDirectory() as t:
            open(f"{t}/a.pdf", "wb").write(d)
            r = subprocess.run(["qpdf", f"{t}/a.pdf", f"{t}/b.pdf"], capture_output=True, text=True)
            print("  qpdf", r.returncode, r.stderr[:200])
            if os.path.exists(f"{t}/b.pdf"):
                d2 = open(f"{t}/b.pdf", "rb").read()
                print("  pdftotext", len(subprocess.run(["pdftotext", f"{t}/b.pdf", "-"], capture_output=True).stdout))
                x = ocr.texto_ocr(d2); print("  ocr reparado", len(x), repr(x[:300]))
