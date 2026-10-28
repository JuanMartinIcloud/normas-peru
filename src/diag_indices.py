"""Diagnostico temporal: analisis de proposiciones convertidas en ley."""
import os
import psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("""SELECT p.numero, a.relevante, a.calificacion, a.puntaje, a.impacto, a.resumen, a.comentario
               FROM proyectos_ley p JOIN analisis a ON a.tipo='P' AND a.ref_id=p.id
               WHERE p.ley_fecha >= current_date - 45""")
for r in cur.fetchall():
    print(r, "\n")
