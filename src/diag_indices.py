import os, json, psycopg2
m = psycopg2.connect(os.environ["DATABASE_URL"]); c = m.cursor()
c.execute("""SELECT a.tipo, coalesce(n.tipo||' '||n.numero, p.numero), coalesce(n.sumilla, p.titulo), a.calificacion, a.impacto, a.sector,
                    a.comites, a.resumen, a.cambios, a.comentario, a.acciones, a.accion_directorio, a.lectura, a.modelo
             FROM analisis a LEFT JOIN normas n ON a.tipo='N' AND n.id=a.ref_id LEFT JOIN proyectos_ley p ON a.tipo='P' AND p.id=a.ref_id
             WHERE a.relevante ORDER BY random() LIMIT 4""")
for r in c.fetchall():
    print(json.dumps(r, ensure_ascii=False, default=str, indent=0)[:2500]); print("=====")
c.execute("""SELECT n.tipo, n.numero, left(n.sumilla,120) FROM analisis a JOIN normas n ON n.id=a.ref_id AND a.tipo='N' WHERE NOT a.relevante ORDER BY random() LIMIT 12""")
for r in c.fetchall(): print("NO REL", r)
c.execute("SELECT calificacion, count(*) FROM analisis WHERE relevante GROUP BY 1"); print(c.fetchall())
