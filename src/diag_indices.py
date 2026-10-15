import os, psycopg2
m = psycopg2.connect(os.environ["DATABASE_URL"]); c = m.cursor()
c.execute("""SELECT to_char(fecha,'YYYY-MM'), count(*) FILTER (WHERE relevante), count(*) FROM analisis WHERE tipo='N' GROUP BY 1 ORDER BY 1""")
print("normas por mes (relevantes, revisadas):", c.fetchall())
c.execute("""SELECT to_char(n.fecha,'YYYY-MM'), count(*) FROM normas n WHERE n.fecha >= '2026-08-01' GROUP BY 1 ORDER BY 1"""); print("normas publicadas:", c.fetchall())
c.execute("""SELECT to_char(fecha,'YYYY-MM'), count(*) FILTER (WHERE relevante), count(*) FROM analisis WHERE tipo='P' GROUP BY 1 ORDER BY 1"""); print("proyectos:", c.fetchall())
c.execute("SELECT clave, valor FROM configuracion WHERE clave LIKE 'historico%'"); print(c.fetchall())
c.execute("SELECT count(*) FROM usuarios"); print("usuarios:", c.fetchone())
c.execute("SELECT max(fecha) FROM seguimientos"); print("ultimo seguimiento:", c.fetchone())
