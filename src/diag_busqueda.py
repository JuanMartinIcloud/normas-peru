"""Mide cuanto tarda cada parte de una busqueda (solo diagnostico)."""
import os, sys, time
import psycopg2

q = sys.argv[1]
salida = []
def medir(nombre, url, sql, params):
    if not url:
        return
    t = time.time()
    try:
        c = psycopg2.connect(url, connect_timeout=60); cur = c.cursor()
        conectar = time.time() - t
        t2 = time.time()
        if os.getenv("SIN_SEQ"):
            cur.execute("SET enable_seqscan = off")
        cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
        plan = "\n".join(r[0] for r in cur.fetchall())
        salida.append(f"## {nombre}: conectar {conectar:.1f}s, consulta {time.time()-t2:.1f}s\n{plan}\n")
        c.close()
    except Exception as e:
        salida.append(f"## {nombre}: ERROR {e}\n")

principal = os.environ["DATABASE_URL"]
tsq = "websearch_to_tsquery('spanish', %s)"
medir("normas sumilla count", principal,
      f"SELECT count(*) FROM normas WHERE to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,'')) @@ {tsq}", (q,))
medir("proyectos count", principal,
      f"SELECT count(*) FROM proyectos_ley WHERE to_tsvector('spanish', coalesce(titulo,'') || ' ' || coalesce(sumilla,'')) @@ {tsq} OR titulo ILIKE %s", (q, f"%{q}%"))
for i in (1, 2, 3, 5, 6, 7, 8, 9):
    url = os.getenv(f"TEXTOS_URL_{i}", "")
    medir(f"texto {i} claves N", url,
          f"SELECT clave FROM documentos WHERE tipo = 'N' AND to_tsvector('spanish', texto) @@ ({tsq}) LIMIT 5000", (q,))
open("sondeo_buscador/diag.txt", "w").write("\n".join(salida))
