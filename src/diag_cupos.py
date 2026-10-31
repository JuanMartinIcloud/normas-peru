"""Diagnostico: transferencia y espacio de todos los proyectos de Neon (solo API, no consulta las bases)."""
import os, requests
API = "https://console.neon.tech/api/v2"
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"}
ps = requests.get(f"{API}/projects", headers=h, timeout=60, params={"org_id": "org-fancy-heart-74067952", "limit": 100}).json().get("projects", [])
print("proyectos:", len(ps))
for p in ps:
    d = requests.get(f"{API}/projects/{p['id']}", headers=h, timeout=60).json().get("project", {})
    br = requests.get(f"{API}/projects/{p['id']}/branches", headers=h, timeout=60).json().get("branches", [])
    tam = sum(b.get("logical_size") or 0 for b in br)
    print(f"{d.get('name'):22} {p['id']:28} transf={ (d.get('data_transfer_bytes') or 0)/1e9:5.2f} GB  tam={tam/1e6:7.1f} MB  ramas={len(br)} region={d.get('region_id')} pg={d.get('pg_version')} logical={ (d.get('settings') or {}).get('enable_logical_replication')} quota={(d.get('settings') or {}).get('quota')}")
r = requests.get(f"{API}/users/me", headers=h, timeout=60).json()
print("plan:", r.get("plan"), "max_autoscaling:", r.get("max_autoscaling_limit"), "projects_limit:", r.get("projects_limit"), "branches_limit:", r.get("branches_limit"))
