import os, psycopg2
for i in (1, 2, 3):
    c = psycopg2.connect(os.environ[f"TEXTOS_URL_{i}"]); cur = c.cursor()
    cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='documentos'")
    print(i, cur.fetchall())
    cur.execute("SELECT i.indexrelid::regclass, i.indisvalid, i.indisready FROM pg_index i WHERE i.indrelid='documentos'::regclass")
    print(i, cur.fetchall())
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    print(i, cur.fetchone())
    c.close()
