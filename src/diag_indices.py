import os, psycopg2
m = psycopg2.connect(os.environ["DATABASE_URL"]); m.autocommit = True; c = m.cursor()
c.execute("CREATE INDEX IF NOT EXISTS idx_proy_clave ON proyectos_ley ((periodo || '|' || camara || '|' || numero))")
c.execute("ANALYZE proyectos_ley")
print("indice creado")
