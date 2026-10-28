"""Diagnostico temporal: analisis de proposiciones convertidas en ley."""
import os
import psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("""SELECT p.numero, a.calificacion, a.puntaje, a.impacto, a.lectura, a.resumen
               FROM proyectos_ley p JOIN analisis a ON a.tipo='P' AND a.ref_id=p.id
               WHERE p.numero IN ('00098-2026-2031-CD', '00013-2026-2031-S')""")
for r in cur.fetchall():
    print(r, "\n")
