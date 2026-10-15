import os, psycopg2
m = psycopg2.connect(os.environ["DATABASE_URL"]); c = m.cursor()
c.execute("SELECT count(*), count(DISTINCT proyecto_id), min(fecha)::date, max(fecha)::date FROM seguimientos"); print("seguimientos", c.fetchone())
c.execute("""SELECT camara, estado, count(*) FROM seguimientos WHERE fecha >= '2026-09-01' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 30""")
for r in c.fetchall(): print(r)
c.execute("""SELECT (fecha AT TIME ZONE 'America/Lima')::date d, camara, estado, comisiones FROM seguimientos WHERE (estado ILIKE '%dictamen%' OR estado ILIKE '%aut_grafa%') ORDER BY fecha DESC LIMIT 12""")
for r in c.fetchall(): print("ULT", r)
c.execute("SELECT tipo, relevante, count(*), min(fecha), max(fecha) FROM analisis GROUP BY 1,2 ORDER BY 1,2"); print(c.fetchall())
c.execute("SELECT clave, valor FROM configuracion WHERE clave LIKE 'historico%'"); print(c.fetchall())
