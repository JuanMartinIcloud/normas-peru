"""Pasa todos los textos de la base de texto 1 (llena y lenta) a la base de texto 12, comprueba que
esten completos y recien entonces vacia la base 1 y la deja con un indice nuevo y ordenado."""
import os
import psycopg2
from psycopg2.extras import execute_values

origen = psycopg2.connect(os.environ["TEXTOS_URL_1"], connect_timeout=60)
destino = psycopg2.connect(os.environ["TEXTOS_URL_12"], connect_timeout=60)
co = origen.cursor()
co.execute("SELECT count(*) FROM documentos")
total = co.fetchone()[0]
print(f"Base 1: {total} documentos")
cur = origen.cursor(name="lector")
cur.itersize = 500
cur.execute("SELECT tipo, clave, estado, texto FROM documentos")
cd = destino.cursor()
copiados = 0
while True:
    filas = cur.fetchmany(500)
    if not filas:
        break
    execute_values(cd, "INSERT INTO documentos (tipo, clave, estado, texto) VALUES %s ON CONFLICT (tipo, clave) DO NOTHING", filas)
    destino.commit()
    copiados += len(filas)
    if copiados % 5000 < 500:
        print(f"  {copiados} copiados")
cur.close()
origen.commit()
# Verificacion: todas las claves de la base 1 deben estar en la 12
co.execute("SELECT tipo, clave FROM documentos")
claves_1 = set(co.fetchall())
cd.execute("SELECT tipo, clave FROM documentos")
claves_12 = set(cd.fetchall())
faltan = claves_1 - claves_12
print(f"Copiados {copiados}; faltan en la base 12: {len(faltan)}")
if faltan:
    raise SystemExit("::error::No se vacia la base 1 porque faltan documentos en la copia.")
origen.autocommit = True
co.execute("TRUNCATE documentos")
co.execute("ALTER INDEX idx_documentos_busqueda SET (fastupdate = off)")
co.execute("VACUUM ANALYZE documentos")
co.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
print(f"Base 1 vaciada; tamaño ahora: {co.fetchone()[0]}")
cd.execute("ANALYZE documentos")
destino.commit()
