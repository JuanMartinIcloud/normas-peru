import os, psycopg2
for i in (1, 12):
    c = psycopg2.connect(os.environ[f"TEXTOS_URL_{i}"]); cur = c.cursor()
    cur.execute("SELECT count(*), pg_size_pretty(pg_database_size(current_database())) FROM documentos")
    print(f"texto {i}:", cur.fetchone())
