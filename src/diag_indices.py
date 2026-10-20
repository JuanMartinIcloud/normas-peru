"""Diagnostico temporal: revision general del sistema (datos al dia, textos, resumenes, monitoreo)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import psycopg2
from indexar import Bases
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(sql, a=None):
    cur.execute(sql, a); return cur.fetchall()
for t in ("resumenes", "analisis", "informes", "busqueda_ejecuciones", "busquedas_guardadas", "seguimientos", "descargas"):
    print(t, [r[0] for r in q("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (t,))])
print("normas por dia:", q("SELECT fecha, count(*) FROM normas WHERE fecha >= current_date - 6 GROUP BY 1 ORDER BY 1"))
print("proyectos por dia:", q("SELECT fecha_presentacion, count(*) FROM proyectos_ley WHERE fecha_presentacion >= current_date - 6 GROUP BY 1 ORDER BY 1"))
print("totales:", q("SELECT (SELECT count(*) FROM normas), (SELECT count(*) FROM proyectos_ley)"))
print("descargas:", q("SELECT * FROM descargas ORDER BY 1 DESC LIMIT 6"))
claves_n = [r[0] for r in q("SELECT hash_unico FROM normas WHERE fecha >= current_date - 6")]
claves_p = [r[0] for r in q("SELECT periodo||'|'||camara||'|'||numero FROM proyectos_ley WHERE fecha_presentacion >= current_date - 30 OR sumilla_revisada IS NOT TRUE")]
print("proyectos sin procesar (sumilla_revisada):", q("SELECT count(*) FROM proyectos_ley WHERE sumilla_revisada IS NOT TRUE AND num_pley IS NOT NULL"))
b = Bases(); docs = {}
for u in b.urls:
    for t, k, e in b.ejecutar(u, lambda cur, n=claves_n, p=claves_p: (cur.execute("SELECT tipo, clave, estado FROM documentos WHERE (tipo='N' AND clave = ANY(%s)) OR (tipo='P' AND clave = ANY(%s))", (n, p)), cur.fetchall())[1]):
        docs[(t, k)] = e
from collections import Counter
print("textos normas ultimos 7 dias:", Counter(docs.get(("N", k), "FALTA") for k in claves_n))
print("textos proyectos recientes:", Counter(docs.get(("P", k), "FALTA") for k in claves_p))
print("cupos:", b.ejecutar(b.control, lambda cur: (cur.execute("SELECT to_regclass('public.cupos')"), cur.fetchall())[1]))
print("avance no terminado:", b.ejecutar(b.control, lambda cur: (cur.execute("SELECT trabajador, cursor, terminado, actualizado FROM avance WHERE NOT terminado"), cur.fetchall())[1]))
