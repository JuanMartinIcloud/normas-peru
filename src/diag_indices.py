"""Diagnostico temporal: prueba de la edicion completa (NL + EX) en normas sin texto."""
import os, sys, random, time
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases, principal, texto_cuadernillo
b = Bases()
claves = []
for url in b.urls:
    claves += b.ejecutar(url, lambda cur: (cur.execute("SELECT clave FROM documentos WHERE tipo='N' AND estado <> 'ok'"), [r[0] for r in cur.fetchall()])[1])
c = principal(); cur = c.cursor()
cur.execute("SELECT fecha, tipo, numero, extraordinaria FROM normas WHERE hash_unico = ANY(%s) ORDER BY fecha", (claves,))
filas = cur.fetchall()
random.seed(5)
ok = 0
for f in random.sample(filas, 10):
    t = time.time()
    x = texto_cuadernillo(f[0], f[2], f[1])
    ok += len(x) >= 100
    print(f, len(x), round(time.time() - t), repr(x[:250]))
print("con texto:", ok, "de 10")
