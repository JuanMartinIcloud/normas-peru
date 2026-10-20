"""Diagnostico temporal: la web responde (paginas y funciones con IA)."""
import time, requests
B = "https://normas-peru.vercel.app"
for ruta in ("/", "/?fecha=2026-10-19", "/buscar?q=teletrabajo", "/buscar?q=piscologica", "/proyectos", "/proyectos?q=pensiones",
             "/resumenes", "/unir", "/ingresar", "/monitoreo", "/api/csv?q=teletrabajo"):
    t = time.time()
    try:
        r = requests.get(B + ruta, timeout=60, allow_redirects=True)
        malo = [x for x in ("No se pudo leer", "Error del servidor", "Application error", "500") if x in r.text[:200000]]
        print(f"{r.status_code} {time.time() - t:5.1f}s {len(r.content):8d} {ruta} {r.url[len(B):] if r.url != B + ruta else ''} {malo}")
    except Exception as e:
        print("ERR", ruta, e)
for path, body in (("/api/ia/interpretar", {"q": "normas sobre teletrabajo en el sector público"}),):
    t = time.time()
    r = requests.post(B + path, json=body, timeout=120)
    print(r.status_code, round(time.time() - t), path, r.text[:300])
