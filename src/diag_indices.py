"""Diagnostico temporal: estado final del indexado."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases, principal
b = Bases()
print("Revisados:", b.ejecutar(b.control, lambda cur: (cur.execute("SELECT tipo, resultado, count(*) FROM ocr_revisado GROUP BY 1, 2 ORDER BY 1, 2"), cur.fetchall())[1]))
docs = {}
for url in b.urls:
    for t, k, e in b.ejecutar(url, lambda cur: (cur.execute("SELECT tipo, clave, estado FROM documentos"), cur.fetchall())[1]):
        docs.setdefault(t, {})
        if docs[t].get(k) != "ok":
            docs[t][k] = e
c = principal(); cur = c.cursor()
cur.execute("SELECT hash_unico, fecha FROM normas"); normas = cur.fetchall()
cur.execute("SELECT periodo||'|'||camara||'|'||numero, fecha_presentacion FROM proyectos_ley"); proy = cur.fetchall()
cur.execute("SELECT fecha, tipo, numero, left(sumilla, 80) FROM normas WHERE hash_unico = ANY(%s) ORDER BY fecha",
            ([k for k, _ in normas if docs["N"].get(k) != "ok"],))
falta = cur.fetchall()
for nombre, filas, t in (("NORMAS", normas, "N"), ("PROYECTOS", proy, "P")):
    est = {}
    for k, f in filas:
        e = docs[t].get(k, "FALTA"); est[e] = est.get(e, 0) + 1
    print(nombre, len(filas), est, "| ultima fecha", max(f for _, f in filas if f))
print("\nNormas sin texto:")
for f in falta: print(" ", f)
