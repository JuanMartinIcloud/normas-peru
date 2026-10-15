"""Mide cada parte de una busqueda con varios terminos (como la busqueda con IA)."""
import os, sys, time, concurrent.futures as cf
import psycopg2

terminos = sys.argv[1].split("|")
out = []
def p(x): print(x); out.append(x)
urls = {i: os.getenv(f"TEXTOS_URL_{i}", "") for i in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12)}
q = " || ".join(["websearch_to_tsquery('spanish', %s)"] * len(terminos))
def claves(i):
    t = time.time(); c = psycopg2.connect(urls[i]); cur = c.cursor(); t1 = time.time()
    cur.execute(f"SELECT clave FROM documentos WHERE tipo='N' AND to_tsvector('spanish', texto) @@ ({q}) LIMIT 5000", terminos)
    r = [x[0] for x in cur.fetchall()]; c.close()
    return i, len(r), t1 - t, time.time() - t1, r
t = time.time()
with cf.ThreadPoolExecutor(12) as ex:
    res = list(ex.map(claves, [i for i in urls if urls[i]]))
todas = []
for i, n, con, con_q, r in res:
    p(f"base {i}: {n} claves, conectar {con:.1f}s, consulta {con_q:.1f}s"); todas += r
p(f"TOTAL claves {len(todas)} en {time.time()-t:.1f}s")
m = psycopg2.connect(os.environ["DATABASE_URL"]); cur = m.cursor()
tsv = "to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,''))"
cond = " OR ".join([f"{tsv} @@ websearch_to_tsquery('spanish', %s)"] * len(terminos)) + " OR hash_unico = ANY(%s)"
for nombre, sql in [("count", f"SELECT count(*) FROM normas WHERE ({cond})"),
                    ("lista por fecha", f"SELECT id FROM normas WHERE ({cond}) ORDER BY fecha DESC LIMIT 20"),
                    ("lista por relevancia", f"SELECT id FROM normas WHERE ({cond}) ORDER BY ts_rank({tsv}, ({q})) DESC LIMIT 20")]:
    t = time.time()
    params = terminos + [todas] + (terminos if "relevancia" in nombre else [])
    cur.execute(sql, params); cur.fetchall()
    p(f"principal {nombre}: {time.time()-t:.1f}s")
open("sondeo_buscador/diag.txt", "w").write("\n".join(out))
