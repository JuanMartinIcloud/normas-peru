"""Diagnostico de SOLO LECTURA (no cambia nada en ninguna base).

    python src/diagnostico.py neon        # transferencia, computo y espacio de cada proyecto (API de Neon)
    python src/diagnostico.py consultas   # consultas que mas filas devolvieron en la base principal
    python src/diagnostico.py conteos     # conteos de control del sistema
    python src/diagnostico.py seguridad   # usuarios, permisos, funciones y disparadores de cada base
    python src/diagnostico.py web         # comprueba desde afuera que la web este cerrada (sin usuario)

El resultado se muestra como un aviso de la ejecucion en GitHub (no se guarda en el repositorio).
"""
import os
import sys

import psycopg2
import requests

import bases

API = "https://console.neon.tech/api/v2"
PREFIJO = "normas-textos-"   # nombre de los proyectos de Neon de este sistema
lineas = []


def p(*x):
    lineas.append(" ".join(str(i) for i in x))


def neon():
    h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"}
    orgs = requests.get(f"{API}/users/me/organizations", headers=h, timeout=60).json().get("organizations") or []
    p(f"cuenta de Neon: verificacion en dos pasos exigida = {[o.get('require_mfa') for o in orgs]}")
    params = {"limit": 100, **({"org_id": orgs[0]["id"]} if orgs else {})}
    for q in requests.get(f"{API}/projects", headers=h, params=params, timeout=60).json().get("projects", []):
        if not str(q.get("name", "")).startswith(PREFIJO):
            continue   # otros proyectos de la cuenta: no son de este sistema y no se muestran (el registro es publico)
        d = requests.get(f"{API}/projects/{q['id']}", headers=h, timeout=60).json().get("project", {})
        br = requests.get(f"{API}/projects/{q['id']}/branches", headers=h, timeout=60).json().get("branches", [])
        tam = sum(b.get("logical_size") or 0 for b in br)
        ajustes = d.get("settings") or {}
        p(f"{d.get('name')}: IPs permitidas {(ajustes.get('allowed_ips') or {}).get('ips') or 'todas'}, "
          f"solo conexiones privadas {ajustes.get('block_public_connections')}")
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
            cur.execute("""SELECT string_agg(relname || ' ' || pg_size_pretty(pg_total_relation_size(oid)) || ' (' ||
                                  reltuples::bigint || ' filas aprox.)', ', ')
                           FROM pg_class WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
                             AND relname IN ('textos')""")
            viejas = cur.fetchone()[0]
            cur.execute("""SELECT string_agg(r.rolname || ' miembros:' || coalesce((SELECT string_agg(m.rolname, '/')
                                  FROM pg_auth_members a JOIN pg_roles m ON m.oid = a.member WHERE a.roleid = r.oid), '-')
                                  || ' tablas:' || (SELECT count(*) FROM information_schema.role_table_grants g
                                                    WHERE g.grantee = r.rolname AND g.table_schema = 'public'), ', ')
                           FROM pg_roles r WHERE r.rolname IN ('token_roles', 'authenticated', 'anonymous', 'authenticator')""")
            api_roles = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()")
            conexiones = cur.fetchone()[0]
            c.close()
            p(f"[{nombre}] roles: {', '.join(roles)} | PUBLIC puede crear objetos: {pub_crear} | PUBLIC puede conectarse: "
              f"{pub_conectar} | permisos de tablas a PUBLIC: {pub_tablas} | funciones propias: {funciones or 'ninguna'} | "
              f"disparadores: {disparadores or 'ninguno'} | extensiones: {ext} | otros esquemas: {esquemas or 'ninguno'} | "
              f"tablas: {tablas} | tablas antiguas: {viejas or 'ninguna'} | roles de acceso por API: {api_roles or 'ninguno'} | "
              f"otras conexiones abiertas: {conexiones}")
        except Exception as e:  # noqa: BLE001
            p(f"[{nombre}] no se pudo revisar: {type(e).__name__}")


def web():
    """Pruebas desde afuera, sin usuario: nada debe mostrar datos."""
    sitio = "https://normas-peru.vercel.app"
    nav = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
    falsa = {"Cookie": "sesion=1.99999999999999." + "a" * 64, **nav}
    pruebas = [
        ("portada sin usuario (espera 307 a /ingresar)", "GET", "/", nav),
        ("proyectos sin usuario (espera 307)", "GET", "/proyectos?q=agua", nav),
        ("monitoreo sin usuario (espera 307)", "GET", "/monitoreo", nav),
        ("descarga Excel sin usuario (espera 401)", "GET", "/api/csv", nav),
        ("estado del sistema sin usuario (espera 401)", "GET", "/api/estado", nav),
        ("IA sin usuario (espera 401)", "POST", "/api/ia/resumir", nav),
        ("robot de Google (espera 403)", "GET", "/", {"User-Agent": "Googlebot/2.1"}),
        ("programa automatico (espera 403)", "GET", "/", {"User-Agent": "python-requests/2.32"}),
        ("sesion falsificada en pagina (no debe mostrar datos)", "GET", "/resumenes", falsa),
        ("sesion falsificada en descarga (espera 401)", "GET", "/api/csv", falsa),
        ("tarea de busquedas con clave falsa (espera 401)", "POST", "/api/busquedas/ejecutar",
         {"x-clave-tareas": "0" * 48, **nav}),
        ("optimizador de imagenes (espera 404)", "GET", "/_next/image?url=%2Fx.svg&w=64&q=75", nav),
        ("pagina de ingreso (espera 200)", "GET", "/ingresar", nav),
        ("robots.txt (espera 200)", "GET", "/robots.txt", nav),
    ]
    for titulo, metodo, ruta, cab in pruebas:
        try:
            r = requests.request(metodo, sitio + ruta, headers=cab, timeout=60, allow_redirects=False)
            extra = r.headers.get("location", "")
            if "falsificada en pagina" in titulo:
                extra = "sin datos" if ("no está disponible" in r.text or r.status_code in (307, 401)) and "sumilla" not in r.text else "MUESTRA DATOS"
            p(f"{titulo}: {r.status_code} {extra}")
        except Exception as e:  # noqa: BLE001
            p(f"{titulo}: error {type(e).__name__}")
    r = requests.get(sitio + "/ingresar", headers=nav, timeout=60)
    p("cabeceras: " + ", ".join(f"{k}={'si' if r.headers.get(k) else 'NO'}" for k in
                                ("x-robots-tag", "x-frame-options", "strict-transport-security", "x-content-type-options"))
      + f", x-powered-by={'PRESENTE' if r.headers.get('x-powered-by') else 'oculto'}")


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "neon"
    {"neon": neon, "consultas": consultas, "conteos": conteos, "seguridad": seguridad, "web": web}[modo]()
    texto = "\n".join(lineas)
    print(texto)
    # Un solo aviso con todo el resultado (los saltos de linea se codifican para GitHub)
    cod = texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title=Diagnostico {modo}::{cod}")


if __name__ == "__main__":
    main()
