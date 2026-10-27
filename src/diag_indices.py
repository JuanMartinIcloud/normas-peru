"""Recupera tipo y numero de antes de la correccion (rama de Neon en un momento anterior) y los vuelve a
separar eligiendo, entre las formas posibles de unir el "NO", la que forma palabras reales (vocabulario).
La rama temporal se borra al terminar. No cambia hash_unico."""
import os, sys, re, time, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
import psycopg2, requests
from elperuano import _separar_titulo
from classifier import clasificar
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY'].strip()}", "Accept": "application/json", "Content-Type": "application/json"}
API = "https://console.neon.tech/api/v2"
PID = "patient-sea-69646257"   # normas-textos-4 (base principal)
ANTES = "2026-10-27T16:20:00Z"  # antes de la correccion (16:27)
br = requests.get(f"{API}/projects/{PID}/branches", headers=h, timeout=60).json()["branches"]
padre = next(b for b in br if b.get("default") or b.get("primary"))
r = requests.post(f"{API}/projects/{PID}/branches", headers=h, timeout=120, json={
    "branch": {"name": "recuperar-titulos", "parent_id": padre["id"], "parent_timestamp": ANTES},
    "endpoints": [{"type": "read_only"}]})
print("rama:", r.status_code, r.text[:200] if r.status_code >= 300 else "")
d = r.json(); bid = d["branch"]["id"]
try:
    uri = d["connection_uris"][0]["connection_uri"]
    for i in range(30):
        try:
            v = psycopg2.connect(uri, connect_timeout=30); break
        except Exception:
            time.sleep(10)
    cv = v.cursor()
    cv.execute(r"SELECT id, tipo, numero, entidad, sumilla FROM normas WHERE numero <> '' AND numero !~ '[0-9]' AND tipo ~* '[a-záéíóúñ]$'")
    viejas = cv.fetchall(); v.close()
finally:
    print("borrar rama:", requests.delete(f"{API}/projects/{PID}/branches/{bid}", headers=h, timeout=60).status_code)
print("recuperadas:", len(viejas))
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("SELECT sin_tilde FROM vocabulario WHERE n >= 2"); voc = {x[0] for x in cur.fetchall()}
voc |= {"no", "de", "la", "el", "y", "a", "en", "al", "del", "los", "las", "por", "con", "entre", "para", "nos", "s"}
st = lambda w: "".join(ch for ch in unicodedata.normalize("NFKD", w.lower()) if not unicodedata.combining(ch))
def puntos(t):
    ws = [st(w) for w in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", t)]
    return sum(1 for w in ws if w in voc) - sum(1 for w in ws if w not in voc)
hechas = 0
for nid, tipo, numero, entidad, sumilla in viejas:
    T = tipo.upper()
    variantes = [f"{T}NO{numero}", f"{T}NO {numero}", f"{T} NO {numero}", f"{T} NO{numero}"]
    mejor = max(variantes, key=puntos)
    t2, n2 = _separar_titulo(mejor)
    k = clasificar(entidad or "", sumilla or "", t2)
    cur.execute("UPDATE normas SET tipo = %s, numero = %s, rubro = %s WHERE id = %s", (t2, n2, k["rubro"], nid))
    hechas += 1
    if hechas <= 40: print(f"  {tipo[:35]!r}|{numero[:25]!r} -> {t2[:80]!r}|{n2!r}")
c.commit()
print("corregidas:", hechas)
