"""Prueba del modulo de monitoreo en la web publicada, con un usuario temporal que se borra al final."""
import hashlib, os, re, secrets, sys, time
import psycopg2, requests

BASE = "https://normas-peru.vercel.app"
db = psycopg2.connect(os.environ["DATABASE_URL"]); db.autocommit = True; cur = db.cursor()
clave = secrets.token_hex(12); sal = secrets.token_bytes(16)
h = hashlib.scrypt(clave.encode(), salt=sal, n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
usuario = f"prueba-{secrets.token_hex(3)}"
cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (%s, 'Prueba automatica', %s, 'admin') RETURNING id",
            (usuario, f"scrypt${sal.hex()}${h.hex()}"))
uid = cur.fetchone()[0]
s = requests.Session()
fallas = 0
SALTAR = os.getenv("SOLO_FINAL") == "1"
def nota(t, m):
    if SALTAR and not t.startswith(("csv", "quitar", "resumen")): return
    print(f"::notice title={t}::{m}"[:1000])
try:
    r = s.get(BASE + "/monitoreo", allow_redirects=False, timeout=60)
    nota("sin sesion", f"HTTP {r.status_code} -> {r.headers.get('location')}")
    r = s.post(BASE + "/api/sesion", json={"accion": "ingresar", "usuario": usuario, "clave": clave}, timeout=60)
    nota("ingresar", f"HTTP {r.status_code} {r.text[:100]}")
    r = s.post(BASE + "/api/sesion", json={"accion": "ingresar", "usuario": usuario, "clave": "malamala"}, timeout=60)
    nota("clave incorrecta", f"HTTP {r.status_code} {r.text[:80]}")
    s2 = requests.Session(); s2.cookies = s.cookies
    paginas = ["/monitoreo?mes=2026-10", "/monitoreo/normas?mes=2026-10", "/monitoreo/normas?mes=2026-10&calificacion=Favorable&sector=Telecomunicaciones",
               "/monitoreo/congreso?fecha=2026-10-13", "/monitoreo/congreso?fecha=2026-10-14", "/monitoreo/impacto?mes=2026-10",
               "/monitoreo/informe?fecha=2026-10-14", "/monitoreo/usuarios"]
    for p in paginas:
        t = time.time(); r = s.get(BASE + p, timeout=120); seg = time.time() - t
        html = r.text
        err = re.search(r"No se pudo (leer|armar)[^<]*</strong><p>([^<]{0,300})", html)
        textos = re.findall(r'class="(?:resumen|ia-pendiente)">([^<]{0,160})', html)[:4]
        tarjetas = html.count("tarjeta-mon")
        if r.status_code != 200 or err: fallas += 1
        nota(f"{p} ({seg:.1f}s)", f"HTTP {r.status_code} tarjetas={tarjetas} error={err.group(2) if err else ''} | {textos}")
    r = s.get(BASE + "/api/monitoreo/csv?vista=normas&mes=2026-10", timeout=120)
    nota("csv normas", f"HTTP {r.status_code} lineas={r.text.count(chr(10))} {r.text[:120]!r}")
    r = s.get(BASE + "/api/monitoreo/csv?vista=congreso&fecha=2026-10-14", timeout=120)
    nota("csv congreso", f"HTTP {r.status_code} lineas={r.text.count(chr(10))}")
    cur.execute("SELECT id FROM analisis WHERE relevante AND NOT excluido ORDER BY id LIMIT 1"); aid = cur.fetchone()[0]
    r = s.post(BASE + "/api/monitoreo/excluir", json={"id": aid, "excluir": True}, timeout=60)
    cur.execute("SELECT excluido, excluido_por FROM analisis WHERE id=%s", (aid,)); ex = cur.fetchone()
    s.post(BASE + "/api/monitoreo/excluir", json={"id": aid, "excluir": False}, timeout=60)
    cur.execute("SELECT excluido FROM analisis WHERE id=%s", (aid,)); ex2 = cur.fetchone()
    nota("quitar y devolver", f"HTTP {r.status_code} tras quitar={ex} tras devolver={ex2}")
    t = time.time(); r = s.post(BASE + "/api/monitoreo/ejecutivo", json={"desde": "2026-10-13", "hasta": "2026-10-14"}, timeout=300)
    d = r.json(); nota(f"resumen ejecutivo ({time.time()-t:.0f}s)", f"HTTP {r.status_code} {str(d.get('error') or d.get('panorama'))[:600]}")
    if r.status_code != 200: fallas += 1
finally:
    cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
    print("usuario temporal borrado")
sys.exit(1 if fallas else 0)
