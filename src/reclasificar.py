"""Vuelve a calcular el rubro de todas las normas y proyectos con el clasificador corregido."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import psycopg2
from psycopg2.extras import execute_values
from classifier import clasificar_rubro

c = psycopg2.connect(os.environ["DATABASE_URL"]); c.autocommit = True; cur = c.cursor()
for tabla, cols in (("normas", "sumilla, tipo"), ("proyectos_ley", "titulo, ''")):
    cur.execute(f"SELECT id, {cols}, rubro FROM {tabla}")
    filas = cur.fetchall()
    cambios = [(i, nuevo) for i, a, b, viejo in filas if (nuevo := clasificar_rubro(a or "", b or "")) != viejo]
    for k in range(0, len(cambios), 2000):
        execute_values(cur, f"UPDATE {tabla} t SET rubro = v.rubro FROM (VALUES %s) AS v(id, rubro) WHERE t.id = v.id",
                       cambios[k:k + 2000], template="(%s::bigint, %s)")
    print(f"{tabla}: {len(filas)} revisadas, {len(cambios)} con rubro corregido")
    cur.execute(f"SELECT rubro, count(*) FROM {tabla} GROUP BY 1 ORDER BY 2 DESC")
    print("  ", " | ".join(f"{r} ({n})" for r, n in cur.fetchall()))
