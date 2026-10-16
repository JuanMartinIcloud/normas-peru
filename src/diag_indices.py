"""Diagnostico temporal: cupo de cada modelo de IA y respuesta de la web a una busqueda con IA."""
import os, requests
k = os.environ["GEMINI_API_KEY"]
for m in ["gemini-flash-latest","gemini-3.5-flash-lite","gemini-3.5-flash","gemini-flash-lite-latest","gemma-4-31b-it","gemma-4-26b-a4b-it","gemini-3.1-flash-lite","gemini-3.1-flash-lite-preview","gemini-3-flash-preview","gemini-3.6-flash","gemini-3.7-flash","gemini-3.8-flash"]:
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": k},
                      json={"contents":[{"parts":[{"text":"di ok"}]}]}, timeout=90)
    print("modelo", m, r.status_code, r.text[:160].replace("\n"," ") if r.status_code!=200 else "")
r = requests.post("https://normas-peru.vercel.app/api/ia/interpretar", json={"q": "normas que afecten las inversiones privadas en minería"}, timeout=120)
print("web interpretar", r.status_code, r.text[:400])
