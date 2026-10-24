"""Cupo mensual de TRANSFERENCIA de cada base de Neon (datos que salen de la base: 5 GB al mes gratis).

    python src/cupos.py            # mide cada base y guarda el resultado (cada hora, tarea "Cupos de Neon")

Regla: ninguna base debe pasar de 4 GB en el mes (se deja 1 GB libre).
- Base de texto que llega a 4 GB: no se le agrega nada mas; lo nuevo va a la siguiente base.
- Base principal que llega a 4 GB: se detienen las tareas que no son indispensables (lectura de
  escaneados, analisis de meses anteriores, revision diaria completa de proyectos); la web y la
  carga diaria de normas, proyectos y reportes siguen funcionando.
La medicion usa la API de Neon (secreto NEON_API_KEY). Sin ese secreto no hay medicion y nada se detiene.
"""
import os
import time
from urllib.parse import urlparse

import psycopg2
import requests

TOPE_BYTES = 4 * 10 ** 9           # 4 GB de los 5 GB gratuitos (Neon cuenta GB de 1000 millones de bytes)
API = "https://console.neon.tech/api/v2"
SQL = """CREATE TABLE IF NOT EXISTS cupos (
    host        TEXT PRIMARY KEY,           -- servidor de la base (de su cadena de conexion)
    base        TEXT NOT NULL,              -- nombre en el sistema (principal, texto 2, ...)
    proyecto    TEXT,                       -- nombre del proyecto en Neon
    transferido BIGINT NOT NULL DEFAULT 0,  -- bytes transferidos en el periodo actual
    periodo     TIMESTAMPTZ,                -- inicio del periodo de Neon
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now())"""


def host(url: str) -> str:
    """Servidor de la base, sin el sufijo "-pooler" (la misma base con o sin pool de conexiones)."""
    h = (urlparse(url).hostname or "").lower()
    return h.replace("-pooler", "")


def bases_del_sistema():
    salida = [("principal", os.getenv("DATABASE_URL") or os.getenv("TEXTOS_URL_4", ""))]
    for i in range(2, 13):
        if i != 4 and os.getenv(f"TEXTOS_URL_{i}", "").strip():
            salida.append((f"texto {i}", os.environ[f"TEXTOS_URL_{i}"]))
    return [(n, u.strip()) for n, u in salida if u.strip()]


def control_url() -> str:
    return os.getenv(f"TEXTOS_URL_{os.getenv('TEXTOS_CONTROL', '2')}", "").strip()


def _leer():
    """{host: bytes transferidos} segun la ultima medicion (vacio si no hay medicion)."""
    url = control_url()
    if not url:
        return {}
    try:
        c = psycopg2.connect(url, connect_timeout=60)
        try:
            with c.cursor() as cur:
                cur.execute("SELECT to_regclass('public.cupos') IS NOT NULL")
                if not cur.fetchone()[0]:
                    return {}
                cur.execute("SELECT host, transferido FROM cupos WHERE actualizado > now() - interval '3 days'")
                return dict(cur.fetchall())
        finally:
            c.close()
    except psycopg2.Error as e:
        print(f"  (no se pudo leer el cupo de transferencia: {str(e)[:120]})")
        return {}


_cache = {"t": 0.0, "datos": {}}


def medidos():
    if time.time() - _cache["t"] > 600:
        _cache["datos"], _cache["t"] = _leer(), time.time()
    return _cache["datos"]


def agotada(url: str) -> bool:
    """True si esa base ya llego al tope de 4 GB de transferencia este mes."""
    return medidos().get(host(url), 0) >= TOPE_BYTES


def principal_agotada() -> bool:
    url = os.getenv("DATABASE_URL") or os.getenv("TEXTOS_URL_4", "")
    if url and agotada(url):
        print("La base principal llego a 4 GB de transferencia este mes: esta tarea no indispensable "
              "se detiene hasta que se renueve el cupo.")
        return True
    return False


def actualizar():
    clave = os.getenv("NEON_API_KEY", "").strip()
    if not clave:
        print("::warning title=Cupos::Falta el secreto NEON_API_KEY: no se puede medir la transferencia.")
        return
    h = {"Authorization": f"Bearer {clave}", "Accept": "application/json"}
    filas = []
    for nombre, url in bases_del_sistema():
        try:
            c = psycopg2.connect(url, connect_timeout=60)
            with c.cursor() as cur:
                cur.execute("SELECT current_setting('neon.project_id')")
                pid = cur.fetchone()[0]
            c.close()
            r = requests.get(f"{API}/projects/{pid}", headers=h, timeout=60)
            r.raise_for_status()
            p = r.json().get("project", {})
        except Exception as e:  # noqa: BLE001
            print(f"::warning title=Cupo {nombre}::No se pudo medir: {str(e)[:200]}")
            continue
        b = int(p.get("data_transfer_bytes") or 0)
        filas.append((host(url), nombre, p.get("name"), b, p.get("consumption_period_start")))
        estado = "TOPE ALCANZADO" if b >= TOPE_BYTES else "ok"
        print(f"{nombre} ({p.get('name')}): {b / 1e9:.2f} GB transferidos de 4 GB permitidos [{estado}]")
        if b >= TOPE_BYTES * 0.8:
            print(f"::warning title=Cupo {nombre}::{b / 1e9:.2f} GB transferidos este mes")
    if not filas:
        return
    c = psycopg2.connect(control_url(), connect_timeout=60)
    with c.cursor() as cur:
        cur.execute(SQL)
        for f in filas:
            cur.execute("""INSERT INTO cupos (host, base, proyecto, transferido, periodo) VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (host) DO UPDATE SET base = EXCLUDED.base, proyecto = EXCLUDED.proyecto,
                               transferido = EXCLUDED.transferido, periodo = EXCLUDED.periodo, actualizado = now()""", f)
    c.commit()
    c.close()


if __name__ == "__main__":
    actualizar()
