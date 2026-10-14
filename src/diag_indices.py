import os, psycopg2
for i in (1,):
    c = psycopg2.connect(os.environ[f"TEXTOS_URL_{i}"]); c.autocommit = True; cur = c.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgstattuple")
        cur.execute("SELECT * FROM pgstatginindex('idx_documentos_busqueda')")
        print("antes", cur.fetchone())
    except Exception as e:
        print("pgstattuple:", e)
    try:
        cur.execute("SELECT gin_clean_pending_list('idx_documentos_busqueda')")
        print("limpieza:", cur.fetchone())
    except Exception as e:
        print("limpieza ERROR:", e)
    try:
        cur.execute("SELECT * FROM pgstatginindex('idx_documentos_busqueda')")
        print("despues", cur.fetchone())
    except Exception as e:
        print("despues:", e)
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    print(i, cur.fetchone())
