"""Prueba de las busquedas guardadas en la web publicada (usuario y busqueda temporales que se borran)."""
import hashlib, os, re, secrets, sys, time
import psycopg2, requests

BASE = "https://normas-peru.vercel.app"
db = psycopg2.connect(os.environ["DATABASE_URL"]); db.autocommit = True; cur = db.cursor()
clave = secrets.token_hex(12); sal = secrets.token_bytes(16)
h = hashlib.scrypt(clave.encode(), salt=sal, n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
usuario = f"prueba-{secrets.token_hex(3)}"
cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (%s, 'Prueba automatica', %s, 'editor') RETURNING id",
            (usuario, f"scrypt${sal.hex()}${h.hex()}"))
uid = cur.fetchone()[0]
s = requests.Session(); bid = None; fallas = 0
def nota(t, m): print(f"::notice title={t}::{str(m)[:900]}")
try:
    s.post(BASE + "/api/sesion", json={"accion": "ingresar", "usuario": usuario, "clave": clave}, timeout=60)
    i = s.post(BASE + "/api/ia/interpretar", json={"q": "cambios tributarios que afecten a las empresas mineras"}, timeout=120).json()
    nota("interpretar", i)
    r = s.post(BASE + "/api/busquedas", json={"accion": "crear", "nombre": "PRUEBA AUTOMATICA", "pregunta": "cambios tributarios que afecten a las empresas mineras",
                                             "terminos": i["terminos"], "frecuencia": "mensual"}, timeout=60)
    bid = r.json().get("id"); nota("crear", r.text)
    t = time.time(); r = s.post(BASE + "/api/busquedas", json={"accion": "ejecutar", "id": bid}, timeout=320)
    nota(f"ejecutar ahora ({time.time()-t:.0f}s)", r.text)
    if r.status_code != 200: fallas += 1
    r = s.get(BASE + f"/monitoreo/busquedas/{bid}", timeout=120)
    resumen = re.search(r"<h4>Resumen</h4><p>([^<]{0,400})", r.text)
    nota("pagina resultados", f"HTTP {r.status_code} resumen={resumen.group(1) if resumen else None} items={r.text.count('<li>')}")
    r = s.get(BASE + "/monitoreo/busquedas", timeout=60); nota("lista", f"HTTP {r.status_code} contiene={'PRUEBA AUTOMATICA' in r.text}")
    r = s.get(BASE + "/buscar?pregunta=x&t=miner%C3%ADa&orden=r", timeout=120); nota("boton guardar en buscador", "Guardar esta búsqueda" in r.text)
    cur.execute("SELECT valor FROM configuracion WHERE clave='clave_tareas'"); ct = cur.fetchone()[0]
    r = requests.post(BASE + "/api/busquedas/ejecutar", headers={"x-clave-tareas": ct}, timeout=320); nota("tarea automatica", r.text)
    r = requests.post(BASE + "/api/busquedas/ejecutar", headers={"x-clave-tareas": "mala"}, timeout=60); nota("clave mala", r.status_code)
finally:
    if bid: cur.execute("DELETE FROM busquedas_guardadas WHERE id = %s", (bid,))
    cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
sys.exit(1 if fallas else 0)
