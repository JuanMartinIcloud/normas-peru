import time, requests
B = "https://normas-peru.vercel.app"
t = time.time()
r = requests.post(B + "/api/ia/interpretar", json={"q": "cambios tributarios que afecten a las empresas mineras"}, timeout=120)
print(r.status_code, round(time.time() - t), r.text[:600])
