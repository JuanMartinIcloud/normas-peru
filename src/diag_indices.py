"""Diagnostico temporal: avance del indexador y espacio."""
import os, psycopg2
c = psycopg2.connect(os.environ["TEXTOS_URL_2"]); cur = c.cursor()
cur.execute("SELECT trabajador, cursor, terminado, procesados, actualizado FROM avance ORDER BY 1"); [print(r) for r in cur.fetchall()]
for i in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12):
    u = os.getenv(f"TEXTOS_URL_{i}", "")
    if not u: continue
    k = psycopg2.connect(u); q = k.cursor()
    q.execute("SELECT pg_database_size(current_database())/1048576, count(*), count(*) FILTER (WHERE creado_en > now() - interval '3 hours') FROM documentos")
    print("base", i, q.fetchone())
