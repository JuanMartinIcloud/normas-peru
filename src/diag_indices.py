"""Diagnostico: que consultas sacan mas datos de la base principal (pg_stat_statements)."""
import os
import psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("SELECT stats_reset FROM pg_stat_statements_info")
print("estadisticas desde:", cur.fetchone())
cur.execute("""SELECT calls, rows, round(rows::numeric / greatest(calls,1), 1), round(total_exec_time::numeric/1000,1),
                      regexp_replace(left(query, 330), '\\s+', ' ', 'g')
               FROM pg_stat_statements ORDER BY rows DESC LIMIT 45""")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT sum(calls), sum(rows) FROM pg_stat_statements"); print("total", cur.fetchone())
cur.execute("""SELECT usename, application_name, client_addr, state, left(query,80) FROM pg_stat_activity WHERE datname = current_database()""")
for r in cur.fetchall(): print("act", r)
