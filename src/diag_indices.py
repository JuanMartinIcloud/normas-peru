"""Diagnostico temporal: tiempo del resumen con IA en la web."""
import time, requests
for amb, filtros in [("normas", {"rubro": "Tributario y Aduanero", "desde": "2026-09-01", "hasta": "2026-09-30"}),
                     ("ambos", {"q": "teletrabajo"})]:
    t = time.time()
    try:
        r = requests.post("https://normas-peru.vercel.app/api/ia/resumir", json={"ambito": amb, "filtros": filtros}, timeout=320)
        print(amb, r.status_code, round(time.time() - t), r.text[:300].replace("\n", " "))
    except Exception as e:
        print(amb, "EXC", round(time.time() - t), e)
