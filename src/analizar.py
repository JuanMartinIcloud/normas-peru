"""Actualiza las estadisticas internas de las bases de texto (para que usen su indice)."""
import os
import psycopg2

for i in (1, 2, 3, 5, 6, 7, 8, 9):
    url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
    if not url:
        continue
    try:
        c = psycopg2.connect(url, connect_timeout=60)
        c.autocommit = True
        cur = c.cursor()
        cur.execute("ANALYZE documentos")
        cur.execute("SELECT n_live_tup, last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE relname = 'documentos'")
        print(f"texto {i}: ANALYZE ok -> {cur.fetchone()}")
        c.close()
    except Exception as e:
        print(f"::warning title=texto {i}::{str(e)[:300]}")
