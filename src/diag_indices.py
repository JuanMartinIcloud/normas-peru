"""Diagnostico temporal: consultas que mas datos sacan de la base principal."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT stats_reset FROM pg_stat_statements_info"); print("desde:", cur.fetchone())
cur.execute("""SELECT calls, rows, left(regexp_replace(query, '\\s+', ' ', 'g'), 260)
               FROM pg_stat_statements WHERE query NOT ILIKE '%pg_%' AND query NOT ILIKE '%neon%'
               ORDER BY rows DESC LIMIT 25""")
for r in cur.fetchall(): print(r)
# tamano promedio de una fila del monitoreo (lo que lee el resumen ejecutivo)
cur.execute("""SELECT count(*), sum(pg_column_size(a.*)) FROM analisis a WHERE a.relevante AND a.fecha >= '2026-09-01'""")
n, b = cur.fetchone(); print("analisis sep-oct:", n, "filas,", round(b / 1048576, 2), "MB")
