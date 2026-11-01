"""Diagnostico de SOLO LECTURA (no cambia nada en ninguna base).

    python src/diagnostico.py neon        # transferencia, computo y espacio de cada proyecto (API de Neon)
    python src/diagnostico.py consultas   # consultas que mas filas devolvieron en la base principal
    python src/diagnostico.py conteos     # conteos de control del sistema

El resultado se muestra como un aviso de la ejecucion en GitHub (no se guarda en el repositorio).
"""
import os
import sys

import psycopg2
import requests

import bases

API = "https://console.neon.tech/api/v2"
lineas = []


def p(*x):
    lineas.append(" ".join(str(i) for i in x))


def neon():
    h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"}
    orgs = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60).json().get("organizations") or []
    params = {"limit": 100, **({"org_id": orgs[0]["id"]} if orgs else {})}
    for q in requests.get(f"{API}/projects", headers=h, params=params, timeout=60).json().get("projects", []):
        d = requests.get(f"{API}/projects/{q['id']}", headers=h, timeout=60).json().get("project", {})
        br = requests.get(f"{API}/projects/{q['id']}/branches", headers=h, timeout=60).json().get("branches", [])
        tam = sum(b.get("logical_size") or 0 for b in br)
        p(f"{d.get('name')}: transferencia {(d.get('data_transfer_bytes') or 0) / 1e9:.2f} GB, "
          f"computo {(d.get('compute_time_seconds') or 0) / 3600:.1f} h, espacio {tam / 1e6:.0f} MB, "
          f"limite de espacio {d.get('branch_logical_size_limit')} MiB, periodo desde {d.get('consumption_period_start')}")


def consultas():
    c = psycopg2.connect(bases.url_principal(), connect_timeout=60)
    cur = c.cursor()
    cur.execute("SELECT stats_reset FROM pg_stat_statements_info")
    p("estadisticas desde:", cur.fetchone()[0])
    cur.execute("""SELECT calls, rows, regexp_replace(left(query, 200), '\\s+', ' ', 'g')
                   FROM pg_stat_statements ORDER BY rows DESC LIMIT 30""")
    for llamadas, filas, q in cur.fetchall():
        p(f"{llamadas} veces, {filas} filas: {q}")
    c.close()


def conteos():
    c = psycopg2.connect(bases.url_principal(), connect_timeout=60)
    cur = c.cursor()
    for titulo, sql in (
        ("proyectos sin sumilla revisada", "SELECT count(*) FROM proyectos_ley WHERE sumilla_revisada IS NOT TRUE"),
        ("proyectos", "SELECT count(*) FROM proyectos_ley"),
        ("normas", "SELECT count(*) FROM normas"),
        ("analisis", "SELECT count(*) FROM analisis"),
        ("tamano de la base principal (MB)", "SELECT pg_database_size(current_database()) / 1e6"),
    ):
        cur.execute(sql)
        p(f"{titulo}: {cur.fetchone()[0]}")
    c.close()


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "neon"
    {"neon": neon, "consultas": consultas, "conteos": conteos}[modo]()
    texto = "\n".join(lineas)
    print(texto)
    # Un solo aviso con todo el resultado (los saltos de linea se codifican para GitHub)
    cod = texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title=Diagnostico {modo}::{cod}")


if __name__ == "__main__":
    main()
