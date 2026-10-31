"""Diagnostico temporal: tablas de la base principal y de la base 11 (tamanos)."""
import os
import psycopg2
SQL = """SELECT c.relname, pg_total_relation_size(c.oid)/1e6, pg_relation_size(c.oid)/1e6, c.reltuples::bigint
         FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND c.relkind='r' ORDER BY 2 DESC"""
for nombre, var in (("PRINCIPAL A (4)", "DATABASE_URL"), ("BASE 11", "TEXTOS_URL_11"), ("BASE 10", "TEXTOS_URL_10")):
    c = psycopg2.connect(os.environ[var]); cur = c.cursor()
    cur.execute(SQL); print("\n==", nombre)
    for r in cur.fetchall(): print("  ", r)
    cur.execute("SELECT pg_database_size(current_database())/1e6, version()"); print("  total MB", cur.fetchone())
    cur.execute("SELECT extname FROM pg_extension"); print("  ext", cur.fetchall())
    cur.execute("SELECT sequence_name FROM information_schema.sequences"); print("  seq", [r[0] for r in cur.fetchall()])
    c.close()
