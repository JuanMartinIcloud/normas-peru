import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("UPDATE normas SET tipo = replace(tipo, 'nitoge no de', 'nitogeno de') WHERE tipo LIKE '%nitoge no de%'"); print("nitogeno", cur.rowcount); c.commit()
cur.execute("""SELECT n.tipo, n.numero, a.relevante, a.calificacion, a.puntaje, a.impacto, a.criterio FROM normas n JOIN analisis a ON a.tipo='N' AND a.ref_id=n.id
               WHERE n.sumilla ILIKE '%buen gobierno corporativo%' AND n.fecha >= '2026-10-01'"""); print(cur.fetchall())
cur.execute("SELECT criterio, count(*) FROM analisis WHERE relevante GROUP BY 1 ORDER BY 1"); print("criterios:", cur.fetchall())
cur.execute("""SELECT left(coalesce(n.tipo||' '||n.numero, 'Proy '||p.numero), 70), a.relevante, a.calificacion, a.puntaje FROM analisis a
               LEFT JOIN normas n ON a.tipo='N' AND n.id=a.ref_id LEFT JOIN proyectos_ley p ON a.tipo='P' AND p.id=a.ref_id
               WHERE a.criterio = 5 ORDER BY a.puntaje DESC""")
for r in cur.fetchall(): print(r)
