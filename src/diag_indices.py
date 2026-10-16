"""Diagnostico temporal: avance de la recuperacion de textos."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases
b = Bases()
print("Revisados:", b.ejecutar(b.control, lambda cur: (cur.execute("SELECT tipo, resultado, count(*) FROM ocr_revisado GROUP BY 1, 2 ORDER BY 1, 2"), cur.fetchall())[1]))
tot = {}
for url in b.urls:
    for t, e, n in b.ejecutar(url, lambda cur: (cur.execute("SELECT tipo, estado, count(*) FROM documentos GROUP BY 1, 2"), cur.fetchall())[1]):
        tot[(t, e)] = tot.get((t, e), 0) + n
print("Documentos:", sorted(tot.items()))
