"""Diagnostico temporal: que es el proyecto normas-peru de Neon y quien lo usa."""
import os, requests, psycopg2
from urllib.parse import urlparse
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY'].strip()}", "Accept": "application/json"}
API = "https://console.neon.tech/api/v2"
org = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60).json()["organizations"][0]["id"]
ps = requests.get(f"{API}/projects", headers=h, params={"limit": 100, "org_id": org}, timeout=60).json()["projects"]
nuestros = {}
for k, v in os.environ.items():
    if k.startswith("TEXTOS_URL_") or k == "DATABASE_URL":
        nuestros[(urlparse(v).hostname or "").replace("-pooler", "")] = k
for p in ps:
    if p["name"] not in ("normas-peru", "normas-textos-4"):
        continue
    d = requests.get(f"{API}/projects/{p['id']}", headers=h, timeout=60).json()["project"]
    print("\n==", p["name"], p["id"], "creado", d.get("created_at"))
    print({k: d.get(k) for k in ("data_transfer_bytes", "written_data_bytes", "compute_time_seconds", "synthetic_storage_size", "quota_reset_at", "owner_id")})
    eps = requests.get(f"{API}/projects/{p['id']}/endpoints", headers=h, timeout=60).json().get("endpoints", [])
    for e in eps:
        print("  endpoint", e.get("host"), e.get("current_state"), "ultimo uso", e.get("last_active"), "suspendido", e.get("suspended_at") or e.get("disabled"), "| en nuestros secretos como:", nuestros.get(e.get("host"), "NO"))
    br = requests.get(f"{API}/projects/{p['id']}/branches", headers=h, timeout=60).json().get("branches", [])
    for b in br:
        print("  rama", b.get("name"), "tamano logico MB", round((b.get("logical_size") or 0) / 1048576), "escrito", b.get("updated_at"))
