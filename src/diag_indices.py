"""Correccion de titulos mal separados: el "NO" final de palabras como GOBIERNO se tomaba como "N°".
Reconstruye el titulo original (tipo en mayusculas + "NO " + resto) y lo vuelve a separar bien.
No cambia hash_unico (clave de la norma y de su texto)."""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
import psycopg2
from elperuano import _separar_titulo
from classifier import clasificar
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute(r"""SELECT id, tipo, numero, entidad, sumilla FROM normas
               WHERE numero <> '' AND numero !~ '[0-9]' AND tipo ~* '[a-záéíóúñ]$'""")
filas = cur.fetchall()
print("candidatas:", len(filas))
cambios = []
for nid, tipo, numero, entidad, sumilla in filas:
    original = f"{tipo.upper()}NO {numero}"
    t2, n2 = _separar_titulo(original)
    if (t2, n2) != (tipo, numero):
        cambios.append((nid, t2, n2, entidad, sumilla, tipo, numero))
for x in cambios[:25]:
    print(f"  {x[5]!r} | {x[6][:40]!r}  ->  {x[1][:70]!r} | {x[2]!r}")
for nid, t2, n2, entidad, sumilla, *_ in cambios:
    k = clasificar(entidad or "", sumilla or "", t2)
    cur.execute("UPDATE normas SET tipo = %s, numero = %s, rubro = %s WHERE id = %s", (t2, n2, k["rubro"], nid))
c.commit()
print("corregidas:", len(cambios))
