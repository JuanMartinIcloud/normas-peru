"""Diagnostico temporal: espacio de cada base y cuanto falta indexar."""
import os, psycopg2
tot_docs = 0; tot_mb_ok = 0; libre = 0
for i in range(1, 13):
    if i == 4: continue
    u = os.getenv(f"TEXTOS_URL_{i}", "")
    if not u: print(i, "sin url"); continue
    c = psycopg2.connect(u); cur = c.cursor()
    cur.execute("SELECT pg_database_size(current_database())/1048576.0")
    mb = float(cur.fetchone()[0])
    cur.execute("SELECT count(*) FILTER (WHERE tipo='N'), count(*) FILTER (WHERE tipo='P') FROM documentos")
    n, p = cur.fetchone()
    print(f"base {i}: {mb:.0f} MB  normas={n} proyectos={p}")
    if i != 1 or not os.getenv("TEXTOS_URL_12"):
        tot_docs += n
    if i != 1: libre += max(0, 400 - mb)
    c.close()
m = psycopg2.connect(os.environ["DATABASE_URL"]); cur = m.cursor()
cur.execute("SELECT count(*) FROM normas"); total = cur.fetchone()[0]
cur.execute("SELECT pg_database_size(current_database())/1048576.0"); print(f"principal: {float(cur.fetchone()[0]):.0f} MB")
cur.execute("SELECT extract(year from fecha)::int, count(*) FROM normas GROUP BY 1 ORDER BY 1"); print("normas por anio", cur.fetchall())
print(f"normas totales={total} indexadas(aprox, sin contar base 1 duplicada)={tot_docs} faltan~{total-tot_docs} espacio libre hasta 400MB={libre:.0f} MB")
c = psycopg2.connect(os.environ["TEXTOS_URL_2"]); cur = c.cursor()
cur.execute("SELECT trabajador, cursor, terminado, procesados FROM avance ORDER BY 1"); [print(r) for r in cur.fetchall()]
