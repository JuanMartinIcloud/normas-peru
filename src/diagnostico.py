"""Diagnostico de SOLO LECTURA (no cambia nada en ninguna base).

    python src/diagnostico.py neon        # transferencia, computo y espacio de cada proyecto (API de Neon)
    python src/diagnostico.py consultas   # consultas que mas filas devolvieron en la base principal
    python src/diagnostico.py conteos     # conteos de control del sistema
    python src/diagnostico.py seguridad   # usuarios, permisos, funciones y disparadores de cada base

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


def seguridad():
    """Revision de seguridad de cada base (solo lectura). No muestra datos, solo la configuracion."""
    lista = [("principal", bases.url_principal())] + [(f"texto {i}", u) for i, u in bases.bases_texto()]
    for nombre, url in lista:
        if not url:
            continue
        try:
            c = psycopg2.connect(url, connect_timeout=60)
            cur = c.cursor()
            cur.execute("""SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles
                           WHERE rolname NOT LIKE 'pg\\_%' ORDER BY 1""")
            roles = [f"{r[0]}{'(login)' if r[1] else ''}{'(SUPER)' if r[2] else ''}{'(crea-roles)' if r[3] else ''}" for r in cur.fetchall()]
            cur.execute("SELECT has_schema_privilege('public', 'public', 'CREATE'), has_database_privilege('public', current_database(), 'CONNECT')")
            pub_crear, pub_conectar = cur.fetchone()
            cur.execute("""SELECT count(*) FROM information_schema.role_table_grants
                           WHERE grantee = 'PUBLIC' AND table_schema = 'public'""")
            pub_tablas = cur.fetchone()[0]
            cur.execute("""SELECT p.proname || ' (' || CASE p.prosecdef WHEN true THEN 'SECURITY DEFINER' ELSE 'normal' END || ')'
                           FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                           LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
                           WHERE n.nspname = 'public' AND d.objid IS NULL""")
            funciones = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT tgname || ' en ' || tgrelid::regclass FROM pg_trigger WHERE NOT tgisinternal")
            disparadores = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT extname FROM pg_extension ORDER BY 1")
            ext = [r[0] for r in cur.fetchall()]
            cur.execute("""SELECT n.nspname FROM pg_namespace n WHERE n.nspname NOT IN ('public', 'information_schema')
                           AND n.nspname NOT LIKE 'pg\\_%'""")
            esquemas = [r[0] for r in cur.fetchall()]
            cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1""")
            tablas = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()")
            conexiones = cur.fetchone()[0]
            c.close()
            p(f"[{nombre}] roles: {', '.join(roles)} | PUBLIC puede crear objetos: {pub_crear} | PUBLIC puede conectarse: "
              f"{pub_conectar} | permisos de tablas a PUBLIC: {pub_tablas} | funciones propias: {funciones or 'ninguna'} | "
              f"disparadores: {disparadores or 'ninguno'} | extensiones: {ext} | otros esquemas: {esquemas or 'ninguno'} | "
              f"tablas: {tablas} | otras conexiones abiertas: {conexiones}")
        except Exception as e:  # noqa: BLE001
            p(f"[{nombre}] no se pudo revisar: {type(e).__name__}")


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "neon"
    {"neon": neon, "consultas": consultas, "conteos": conteos, "seguridad": seguridad}[modo]()
    texto = "\n".join(lineas)
    print(texto)
    # Un solo aviso con todo el resultado (los saltos de linea se codifican para GitHub)
    cod = texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title=Diagnostico {modo}::{cod}")


if __name__ == "__main__":
    main()
