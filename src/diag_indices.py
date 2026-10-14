import os, psycopg2
m = psycopg2.connect(os.environ["DATABASE_URL"]); cm = m.cursor()
cm.execute("""SELECT fecha, url_detalle, url_pdf FROM normas WHERE url_detalle NOT LIKE '%%/dispositivo/%%'
              AND url_detalle !~ '-[0-9]+-[0-9]+/?$' ORDER BY random() LIMIT 12""")
for r in cm.fetchall(): print(r)
cm.execute("""SELECT extract(year from fecha)::int, count(*) FROM normas WHERE url_detalle NOT LIKE '%%/dispositivo/%%'
              AND url_detalle !~ '-[0-9]+-[0-9]+/?$' GROUP BY 1 ORDER BY 1""")
print(cm.fetchall())
