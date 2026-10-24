"""Diagnostico temporal: consumo de todos los proyectos de la cuenta de Neon (API)."""
import os, requests
h = {"Authorization": f"Bearer {os.environ.get('NEON_API_KEY', '').strip()}", "Accept": "application/json"}
API = "https://console.neon.tech/api/v2"
r = requests.get(f"{API}/projects", headers=h, params={"limit": 100}, timeout=60)
print("lista:", r.status_code, r.text[:300] if r.status_code != 200 else "")
if r.status_code != 200:
    r2 = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60); print("orgs:", r2.status_code, r2.text[:500])
tot_alm = 0
for p in r.json().get("projects", []) if r.status_code == 200 else []:
    d = requests.get(f"{API}/projects/{p['id']}", headers=h, timeout=60).json().get("project", {})
    alm = (d.get("synthetic_storage_size") or 0); tot_alm += alm
    print(f"{d.get('name'):28s} transf {((d.get('data_transfer_bytes') or 0)/1024**3):5.2f} GB | espacio {alm/1024**2:7.0f} MB | computo {((d.get('compute_time_seconds') or 0)/3600):5.1f} h | periodo {d.get('consumption_period_start')} a {d.get('consumption_period_end')}")
print(f"ESPACIO TOTAL: {tot_alm/1024**3:.2f} GB")
