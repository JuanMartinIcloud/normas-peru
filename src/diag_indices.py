"""Diagnostico temporal: las normas que siguen sin texto despues del OCR."""
import os, sys, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases, principal, pdf_norma, texto_pdf
import ocr
b = Bases()
def f(cur):
    cur.execute("SELECT clave FROM ocr_revisado WHERE tipo='N' AND resultado='sin_texto'")
    return [r[0] for r in cur.fetchall()]
claves = b.ejecutar(b.control, f)
c = principal(); cur = c.cursor()
cur.execute("SELECT hash_unico, fecha, tipo, numero, entidad, left(sumilla, 160), url_detalle FROM normas WHERE hash_unico = ANY(%s)", (claves,))
for k, fecha, tipo, num, ent, sum_, url in cur.fetchall():
    print(f"\n{fecha} {tipo} {num} | {ent} | {sum_}\n  {url}")
    d = pdf_norma(url, fecha)
    if not d:
        print("  sin PDF"); continue
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(d); t.flush()
        print("  ", subprocess.run(["pdfinfo", t.name], capture_output=True, text=True).stdout.replace("\n", " | ")[:400])
        print("   imagenes:", subprocess.run(["pdfimages", "-list", t.name], capture_output=True, text=True).stdout[:600])
    print("  bytes", len(d), "pypdf", len(texto_pdf(d)), "ocr", len(ocr.texto_ocr(d)), repr(ocr.texto_ocr(d)[:200]))
