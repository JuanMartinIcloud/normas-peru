"""Diagnostico temporal: que consultas sacan mas datos de la base principal (trafico de red)."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT extname FROM pg_extension"); print("ext:", [r[0] for r in cur.fetchall()])
try:
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    cur.execute("SELECT stats_reset FROM pg_stat_statements_info"); print("desde:", cur.fetchall())
    cur.execute("""SELECT calls, rows, round(rows::numeric / greatest(calls, 1)) AS filas_por_llamada,
                          left(regexp_replace(query, '\\s+', ' ', 'g'), 230)
                   FROM pg_stat_statements ORDER BY rows DESC LIMIT 30""")
    for r in cur.fetchall(): print(r)
except Exception as e:
    print("pg_stat_statements:", e)
cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))"); print("tamano:", cur.fetchone())
cur.execute("""SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables
               ORDER BY pg_total_relation_size(relid) DESC LIMIT 12"""); print(cur.fetchall())
cur.execute("SELECT usename, application_name, client_addr, count(*) FROM pg_stat_activity GROUP BY 1,2,3"); print(cur.fetchall())
