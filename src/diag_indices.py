"""Diagnostico temporal: tamano (bytes) de lo que leen las tareas de la base principal."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def medir(nombre, sql):
    cur.execute(f"SELECT count(*), sum(pg_column_size(t.*)) FROM ({sql}) t"); n, b = cur.fetchone()
    print(f"{nombre}: {n} filas, {round((b or 0) / 1048576, 2)} MB")
medir("indexar proyectos (cada trabajador)", "SELECT periodo, camara, numero, num_pley, coalesce(titulo, '') FROM proyectos_ley WHERE num_pley IS NOT NULL")
medir("indexar normas recientes (todos)", "SELECT hash_unico, fecha, url_detalle FROM normas WHERE fecha >= current_date - 7")
medir("ocr: proyectos (cada trabajador)", "SELECT periodo || '|' || camara || '|' || numero, periodo, camara, num_pley, coalesce(titulo, '') FROM proyectos_ley")
medir("verificar / diag: todas las normas", "SELECT hash_unico, fecha, url_detalle FROM normas")
medir("diag: hash y fecha", "SELECT hash_unico, fecha FROM normas")
medir("monitoreo: normas de un mes", "SELECT n.id, n.fecha, n.tipo, n.numero, n.entidad, n.sumilla, n.hash_unico, n.url_detalle FROM normas n WHERE n.fecha >= current_date - 30")
medir("csv portada 50 000", "SELECT * FROM normas ORDER BY fecha DESC LIMIT 50000")
medir("todas las sumillas", "SELECT id, sumilla, tipo, entidad FROM normas")
