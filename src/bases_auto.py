"""Bases automaticas: mantiene el registro de bases del sistema y crea bases nuevas en Neon cuando hacen falta.

    python src/bases_auto.py      # lo corre "Cupos de Neon" cada hora

- Anota en el registro (base de control, tabla bases_extra) la conexion de las bases principales fijas
  (4, 9, 10 y 11), para que todas las tareas y la web puedan usar cualquiera de ellas.
- Bases de texto: si entre todas quedan menos de 150 MB libres, crea una base nueva en Neon (gratuita) y
  el indexador empieza a usarla sola. No hay que esperar a que se llenen.
- Bases principales: si ninguna de las disponibles puede recibir la copia, src/cambiar_principal.py llama a
  crear("principal") y la rotacion sigue con la nueva.

Limites del plan gratuito de Neon: 100 proyectos, 1 GB por proyecto y 20 GB en total, 5 GB de
transferencia al mes por proyecto.
"""
import os

import psycopg2
import requests

import principal

API = "https://console.neon.tech/api/v2"
ORG = os.getenv("NEON_ORG_ID", "org-fancy-heart-74067952")
REGION = os.getenv("NEON_REGION", "aws-us-east-1")
LIMITE_TEXTO_MB = int(os.getenv("TEXTOS_LIMITE_MB", "400"))   # el mismo limite que usa el indexador
MIN_LIBRE_TEXTO_MB = 150
MAX_ESPACIO_CUENTA_MB = 18000                                  # de los 20 GB de la cuenta, con margen


def _cabeceras():
    clave = os.getenv("NEON_API_KEY", "").strip()
    if not clave:
        raise RuntimeError("falta el secreto NEON_API_KEY")
    return {"Authorization": f"Bearer {clave}", "Accept": "application/json", "Content-Type": "application/json"}


def preparar():
    principal._control(principal.SQL)


def registrar_fijas():
    """Guarda en el registro la conexion de las principales fijas (solo esta tarea tiene todos los secretos)."""
    preparar()
    for n in principal.FIJAS_PRINCIPALES:
        url = os.getenv(f"TEXTOS_URL_{n}", "").strip()
        if url:
            principal._control("""INSERT INTO bases_extra (numero, rol, url) VALUES (%s, 'principal', %s)
                                  ON CONFLICT (numero) DO UPDATE SET rol = 'principal', url = EXCLUDED.url""", (n, url))
    principal._reg["t"] = 0


def tamano_mb(url):
    c = psycopg2.connect(url, connect_timeout=60)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database()) / 1048576.0")
            return float(cur.fetchone()[0])
    finally:
        c.close()


def espacio_cuenta_mb():
    r = requests.get(f"{API}/projects", headers=_cabeceras(), params={"org_id": ORG, "limit": 100}, timeout=60)
    r.raise_for_status()
    return sum((p.get("synthetic_storage_size") or 0) for p in r.json().get("projects", [])) / 1e6, len(r.json().get("projects", []))


def crear(rol):
    """Crea un proyecto nuevo en Neon, lo anota en el registro y devuelve su numero."""
    preparar()
    usados = {int(n) for (n,) in principal._control("SELECT numero FROM bases_extra")} | set(range(1, 13))
    numero = max(usados) + 1
    try:
        mb, cuantos = espacio_cuenta_mb()
        if cuantos >= 95 or mb >= MAX_ESPACIO_CUENTA_MB:
            raise RuntimeError(f"la cuenta de Neon esta cerca de su limite ({cuantos} proyectos, {mb:.0f} MB)")
    except requests.RequestException as e:
        print(f"  (no se pudo revisar el espacio de la cuenta: {e})")
    cuerpo = {"project": {"name": f"normas-auto-{numero}", "region_id": REGION, "pg_version": 18, "org_id": ORG}}
    r = requests.post(f"{API}/projects", headers=_cabeceras(), json=cuerpo, timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"Neon no creo la base ({r.status_code}): {r.text[:300]}")
    d = r.json()
    url = d["connection_uris"][0]["connection_uri"]
    principal._control("INSERT INTO bases_extra (numero, rol, url, proyecto) VALUES (%s, %s, %s, %s)",
                       (numero, rol, url, d["project"]["id"]))
    principal._reg["t"] = 0
    print(f"::notice title=Base nueva::Se creo en Neon la base normas-auto-{numero} ({rol}); el sistema ya la usa.")
    return numero


def revisar_textos():
    libre = 0.0
    for i, url in principal.bases_texto():
        try:
            libre += max(0.0, LIMITE_TEXTO_MB - tamano_mb(url))
        except psycopg2.Error as e:
            print(f"  base de texto {i} no respondio: {str(e)[:100]}")
    print(f"::notice title=Espacio para textos::{libre:.0f} MB libres entre las bases de texto (se crea una nueva si baja de {MIN_LIBRE_TEXTO_MB} MB)")
    if libre < MIN_LIBRE_TEXTO_MB:
        crear("texto")


def main():
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--crear" and sys.argv[2] in ("texto", "principal"):
        registrar_fijas()
        crear(sys.argv[2])
        return
    if not principal.control_url():
        raise SystemExit("Falta el secreto TEXTOS_URL_2 (base de control).")
    registrar_fijas()
    try:
        revisar_textos()
    except Exception as e:  # noqa: BLE001
        print(f"::error title=Bases automaticas::No se pudo crear la base de texto nueva: {str(e)[:400]}")
        raise SystemExit(1)
    print("::notice title=Bases del sistema::Principales:", ", ".join(str(n) for n in principal.principales()),
          "| activa:", principal.activa(),
          "| de texto:", ", ".join(str(i) for i, _ in principal.bases_texto()))


if __name__ == "__main__":
    main()
