"""Diagnostico temporal: comprobar el sistema tras eliminar el proyecto normas-peru de Neon."""
import os, requests, psycopg2
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY'].strip()}", "Accept": "application/json"}
API = "https://console.neon.tech/api/v2"
org = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60).json()["organizations"][0]["id"]
nombres = [p["name"] for p in requests.get(f"{API}/projects", headers=h, params={"limit": 100, "org_id": org}, timeout=60).json()["projects"]]
print("proyectos:", len(nombres), "| normas-peru sigue:", "normas-peru" in nombres)
for k in ["DATABASE_URL"] + [f"TEXTOS_URL_{i}" for i in range(2, 13) if i != 4]:
    u = os.environ.get(k, "").strip()
    if not u: continue
    try:
        c = psycopg2.connect(u, connect_timeout=60); cur = c.cursor(); cur.execute("SELECT 1"); c.close(); print(k, "ok")
    except Exception as e:
        print(k, "ERROR", str(e)[:120])
B = "https://normas-peru.vercel.app"
for r in ("/", "/buscar?q=teletrabajo", "/proyectos", "/resumenes", "/ingresar"):
    x = requests.get(B + r, timeout=60); print(x.status_code, r, "No se pudo leer" in x.text)
