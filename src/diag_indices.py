"""Diagnostico temporal: espacio (tamano logico) de cada proyecto de la cuenta de Neon."""
import os, requests
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY'].strip()}", "Accept": "application/json"}
API = "https://console.neon.tech/api/v2"
org = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60).json()["organizations"][0]["id"]
tot = 0
for p in requests.get(f"{API}/projects", headers=h, params={"limit": 100, "org_id": org}, timeout=60).json()["projects"]:
    br = requests.get(f"{API}/projects/{p['id']}/branches", headers=h, timeout=60).json().get("branches", [])
    mb = sum((b.get("logical_size") or 0) for b in br) / 1048576
    tot += mb
    print(f"{p['name']:28s} {mb:7.0f} MB  ramas {len(br)}")
print(f"TOTAL {tot:.0f} MB = {tot/1024:.2f} GB")
