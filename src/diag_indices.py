"""Diagnostico temporal: proyectos 'sin_texto' (PDF sin texto legible). Muestra y revision de archivos."""
import os, sys, base64, random, psycopg2, requests
sys.path.insert(0, os.path.dirname(__file__))
from textos import API_CONGRESO, CABECERAS_CONGRESO, cifrar, texto_pdf

principal = os.environ["DATABASE_URL"]
urls = [os.environ[f"TEXTOS_URL_{i}"] for i in range(2, 13) if os.getenv(f"TEXTOS_URL_{i}", "").strip()]
sin = set()
for u in urls:
    c = psycopg2.connect(u); cur = c.cursor()
    try:
        cur.execute("SELECT clave FROM documentos WHERE tipo='P' AND estado='sin_texto'"); sin |= {r[0] for r in cur.fetchall()}
    except Exception: pass
    c.close()
c = psycopg2.connect(principal); cur = c.cursor()
cur.execute("SELECT periodo, camara, numero, num_pley, fecha_presentacion FROM proyectos_ley")
filas = {f"{p}|{ca}|{n}": (p, ca, n, np, f) for p, ca, n, np, f in cur.fetchall()}
c.close()
por = {}
for k in sin:
    if k in filas:
        f = filas[k][4]; y = str(f)[:4] if f else "?"
        por[(filas[k][0], filas[k][1], y)] = por.get((filas[k][0], filas[k][1], y), 0) + 1
print("sin_texto por periodo/camara/anio:", sorted(por.items()))
random.seed(1)
for k in random.sample(sorted(sin), 8):
    p, ca, n, np, f = filas[k]
    r = requests.get(f"{API_CONGRESO}/expediente/{cifrar(p)}/{cifrar(np)}", params={"codTipoParl": ca or "C"}, headers=CABECERAS_CONGRESO, timeout=60)
    exp = (r.json() or {}).get("data") or {}
    arch = [a for s in (exp.get("seguimientos") or []) for a in (s.get("archivos") or [])]
    print(f"\n{k} {f}: {len(arch)} archivos")
    for a in arch[:8]:
        if not a.get("proyectoArchivoId"): continue
        cod = base64.b64encode(str(a["proyectoArchivoId"]).encode()).decode()
        rp = requests.get(f"{API_CONGRESO}/archivo/{cod}/pdf", headers=CABECERAS_CONGRESO, timeout=120)
        t = texto_pdf(rp.content) if rp.content[:4] == b"%PDF" else ""
        print(f"   {str(a.get('nombreArchivo'))[:50]!r} {str(a.get('descripcion'))[:40]!r} bytes={len(rp.content)} texto={len(t or '')}")
