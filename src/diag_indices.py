"""Diagnostico temporal: identificar en Neon el proyecto de la base 1 (retirada)."""
import os, re, psycopg2
from urllib.parse import urlparse
for i in (1, 12):
    u = os.getenv(f"TEXTOS_URL_{i}", "")
    if not u: print(i, "sin url"); continue
    host = urlparse(u).hostname or ""
    ep = host.split(".")[0].replace("-pooler", "")
    c = psycopg2.connect(u); cur = c.cursor()
    cur.execute("SELECT name, setting FROM pg_settings WHERE name ILIKE 'neon.%' AND (name ILIKE '%project%' OR name ILIKE '%endpoint%' OR name ILIKE '%branch%' OR name ILIKE '%timeline%' OR name ILIKE '%tenant%')")
    ajustes = cur.fetchall()
    cur.execute("SELECT current_database(), pg_database_size(current_database())/1048576")
    print(f"base {i}: endpoint={ep} region={'.'.join(host.split('.')[1:3])} db={cur.fetchone()} ajustes={ajustes}")
