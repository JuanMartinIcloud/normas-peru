"""Compara formas de consultar normas con una lista grande de claves (como hace la web, con parametros)."""
import os, sys, time, concurrent.futures as cf
import psycopg2

terminos = sys.argv[1].split("|")
out = []
def p(x): print(x); out.append(x)
urls = [os.getenv(f"TEXTOS_URL_{i}", "") for i in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12)]
qq = " || ".join(["websearch_to_tsquery('spanish', %s)"] * len(terminos))
def claves(u):
    c = psycopg2.connect(u); cur = c.cursor()
    cur.execute(f"SELECT clave FROM documentos WHERE tipo='N' AND to_tsvector('spanish', texto) @@ ({qq}) LIMIT 5000", terminos)
    r = [x[0] for x in cur.fetchall()]; c.close(); return r
with cf.ThreadPoolExecutor(12) as ex:
    keys = [k for r in ex.map(claves, [u for u in urls if u]) for k in r]
p(f"claves: {len(keys)}")
m = psycopg2.connect(os.environ["DATABASE_URL"]); cur = m.cursor()
cur.execute("SELECT indexdef FROM pg_indexes WHERE tablename='normas'"); p(str([r[0][:90] for r in cur.fetchall()]))
tsv = "to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,''))"
n = len(terminos)
qs = " || ".join([f"websearch_to_tsquery('spanish', ${i+1})" for i in range(n)])
k = f"${n+1}"
tipos = ", ".join(["text"] * n + ["text[]"])
cond_ts = " OR ".join([f"{tsv} @@ websearch_to_tsquery('spanish', ${i+1})" for i in range(n)])
variantes = {
    "A ANY": f"({cond_ts} OR hash_unico = ANY({k}))",
    "B IN unnest": f"({cond_ts} OR hash_unico IN (SELECT unnest({k})))",
    "C id IN join": f"({cond_ts} OR id IN (SELECT n2.id FROM normas n2 JOIN unnest({k}) AS u(h) ON n2.hash_unico = u.h))",
    "D union": f"id IN (SELECT id FROM normas WHERE {cond_ts} UNION SELECT n2.id FROM normas n2 JOIN unnest({k}) AS u(h) ON n2.hash_unico = u.h)",
}
cur.execute("SET plan_cache_mode = force_generic_plan")
for nombre, w in variantes.items():
    for etiqueta, sql in [("conteo", f"SELECT count(*) FROM normas WHERE {w}"),
                          ("lista rel", f"SELECT id FROM normas WHERE {w} ORDER BY ts_rank({tsv}, ({qs})) DESC, fecha DESC LIMIT 20")]:
        nom = "x" + str(abs(hash(nombre + etiqueta)))
        cur.execute(f"PREPARE {nom} ({tipos}) AS {sql}")
        t = time.time()
        cur.execute(f"EXECUTE {nom} ({', '.join(['%s'] * (n + 1))})", terminos + [keys]); cur.fetchall()
        p(f"{nombre} {etiqueta}: {time.time()-t:.2f}s")
        cur.execute(f"DEALLOCATE {nom}")
open("sondeo_buscador/diag.txt", "w").write("\n".join(out))
