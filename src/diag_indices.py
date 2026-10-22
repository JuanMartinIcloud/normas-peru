"""Diagnostico temporal: calificaciones del monitoreo en octubre 2026, con ejemplos."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("""SELECT tipo, calificacion, impacto, count(*) FROM analisis
               WHERE fecha BETWEEN '2026-10-01' AND '2026-10-31' AND relevante AND NOT coalesce(excluido, false)
               GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""")
for r in cur.fetchall(): print(r)
cur.execute("""SELECT a.tipo, a.impacto, coalesce(n.tipo || ' ' || n.numero, 'Proy ' || p.numero), left(coalesce(n.sumilla, p.titulo), 110), left(a.comentario, 260)
               FROM analisis a LEFT JOIN normas n ON a.tipo = 'N' AND n.id = a.ref_id LEFT JOIN proyectos_ley p ON a.tipo = 'P' AND p.id = a.ref_id
               WHERE a.fecha BETWEEN '2026-10-01' AND '2026-10-31' AND a.relevante AND a.calificacion = 'Favorable'
                 AND NOT coalesce(a.excluido, false) ORDER BY random() LIMIT 14""")
for r in cur.fetchall(): print("\n", r)
