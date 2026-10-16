"""Diagnostico temporal: avance del indexador y cobertura de textos."""
import os, psycopg2
c = psycopg2.connect(os.environ["TEXTOS_URL_2"]); cur = c.cursor()
cur.execute("SELECT trabajador, cursor, terminado, procesados, actualizado FROM avance ORDER BY 1"); [print(r) for r in cur.fetchall()]
tot = {}
for i in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12):
    u = os.getenv(f"TEXTOS_URL_{i}", "")
    if not u: continue
    k = psycopg2.connect(u); q = k.cursor()
    q.execute("SELECT pg_database_size(current_database())/1048576, estado, count(*) FROM documentos WHERE tipo='N' GROUP BY estado")
    for mb, e, n in q.fetchall(): tot[e] = tot.get(e, 0) + n; mbs = mb
    print("base", i, round(float(mbs)) if q.rowcount else "-")
m = psycopg2.connect(os.environ["DATABASE_URL"]).cursor(); m.execute("SELECT count(*) FROM normas"); print("normas", m.fetchone()[0], "documentos por estado", tot)
