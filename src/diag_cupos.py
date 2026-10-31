"""Diagnostico: transferencia de la base principal (solo API de Neon, no consulta la base)."""
import os, requests
API = "https://console.neon.tech/api/v2"
h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"}
p = requests.get(f"{API}/projects/patient-sea-69646257", headers=h, timeout=60).json().get("project", {})
for k in ("name", "data_transfer_bytes", "consumption_period_start", "consumption_period_end", "compute_time_seconds",
          "active_time_seconds", "synthetic_storage_size"):
    print(k, p.get(k))
print("GB", (p.get("data_transfer_bytes") or 0) / 1e9)
for gran in ("daily", "hourly"):
    r = requests.get(f"{API}/consumption_history/projects", headers=h, timeout=60,
                     params={"project_ids": "patient-sea-69646257", "from": "2026-10-20T00:00:00Z", "to": "2026-10-31T23:00:00Z",
                             "granularity": gran, "org_id": "org-fancy-heart-74067952"})
    print(gran, r.status_code, r.text[:3000])
