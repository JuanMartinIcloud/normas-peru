"""Diagnostico temporal: espacio que ocupa cada base del sistema."""
import os, psycopg2
tot = 0
bases = [("principal", os.environ["DATABASE_URL"])] + [(f"texto {i}", os.environ[f"TEXTOS_URL_{i}"]) for i in range(2, 13) if i != 4 and os.getenv(f"TEXTOS_URL_{i}", "").strip()]
for n, u in bases:
    c = psycopg2.connect(u, connect_timeout=60); cur = c.cursor()
    cur.execute("SELECT pg_database_size(current_database()), current_setting('neon.project_id')")
    b, pid = cur.fetchone(); c.close(); tot += b
    print(f"{n}: {b / 1048576:.0f} MB ({pid})")
print(f"TOTAL: {tot / 1048576:.0f} MB = {tot / 1024 ** 3:.2f} GB en {len(bases)} bases")
