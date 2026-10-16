"""Diagnostico temporal: cuanto esta indexado (texto completo) de normas y proyectos, incluido hoy."""
import os, psycopg2
from datetime import date, timedelta

principal = os.environ["DATABASE_URL"]
urls = [principal] + [os.environ[f"TEXTOS_URL_{i}"] for i in range(2, 13) if os.getenv(f"TEXTOS_URL_{i}", "").strip()]

def q(url, sql, args=None):
    c = psycopg2.connect(url); cur = c.cursor(); cur.execute(sql, args); r = cur.fetchall(); c.close(); return r

hoy = date.today()
print("Fecha del servidor:", hoy)
normas = q(principal, "SELECT hash_unico, fecha FROM normas")
proy = q(principal, "SELECT periodo||'|'||camara||'|'||numero, fecha_presentacion FROM proyectos_ley")
print("Normas en la base:", len(normas), "| ultima fecha:", max(f for _, f in normas))
print("Proyectos en la base:", len(proy), "| ultima presentacion:", max((f for _, f in proy if f), default=None))

docs = {"N": {}, "P": {}}
for i, u in enumerate(urls):
    try:
        rows = q(u, "SELECT tipo, clave, estado FROM documentos")
    except Exception as e:
        print("base", i, "sin tabla documentos:", str(e)[:80]); continue
    for t, k, e in rows:
        docs[t][k] = e
    print("base", i, ":", len(rows), "documentos")

for nombre, filas, t in [("NORMAS", normas, "N"), ("PROYECTOS", proy, "P")]:
    d = docs[t]
    est = {}
    falt = []
    for k, f in filas:
        e = d.get(k)
        est[e or "FALTA"] = est.get(e or "FALTA", 0) + 1
        if not e: falt.append(f)
    print(f"\n{nombre}: {est}")
    if falt:
        por = {}
        for f in falt: por[str(f)[:7] if f else "sin fecha"] = por.get(str(f)[:7] if f else "sin fecha", 0) + 1
        print("  faltantes por mes:", dict(sorted(por.items())[-15:]))
    for dia in [hoy, hoy - timedelta(days=1), hoy - timedelta(days=2)]:
        tot = [k for k, f in filas if f == dia]
        hechos = [k for k in tot if k in d]
        print(f"  {dia}: {len(tot)} en la base, {len(hechos)} indexados")
