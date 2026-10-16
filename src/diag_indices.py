"""Diagnostico temporal: avance del OCR."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases
b = Bases()
def f(cur):
    cur.execute("SELECT tipo, resultado, count(*) FROM ocr_revisado GROUP BY 1, 2 ORDER BY 1, 2")
    return cur.fetchall()
print("Revisados:", b.ejecutar(b.control, f))
def g(cur):
    cur.execute("SELECT tipo, clave FROM ocr_revisado WHERE resultado = 'ok' ORDER BY revisado_en DESC LIMIT 2")
    return cur.fetchall()
ult = b.ejecutar(b.control, g)
total_sin = 0
for url in b.urls:
    def h(cur):
        cur.execute("SELECT tipo, estado, count(*) FROM documentos WHERE estado <> 'sin_pdf' GROUP BY 1, 2")
        return cur.fetchall()
    print(b.ejecutar(url, h))
    for t, k in ult:
        def m(cur, t=t, k=k):
            cur.execute("SELECT estado, length(texto), substr(texto, 1, 600) FROM documentos WHERE tipo=%s AND clave=%s", (t, k))
            return cur.fetchall()
        for r in b.ejecutar(url, m):
            print("\n", t, k, r[0], r[1], "\n", r[2])
