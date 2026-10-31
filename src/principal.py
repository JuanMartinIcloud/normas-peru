"""Base principal activa: hay DOS copias posibles y el sistema usa una a la vez.

    A = normas-textos-4  (secreto TEXTOS_URL_4)
    B = normas-textos-11 (secreto TEXTOS_URL_11)

Cada proyecto de Neon tiene su propio cupo de 5 GB de transferencia al mes. Cuando la base activa se
acerca al limite, src/cambiar_principal.py copia todo a la otra y el sistema (tareas y web) pasa a usar
esa. La que deja de usarse descansa hasta que su cupo se renueve el dia 1.

La base activa se anota en la base de control (TEXTOS_URL_2), tabla "principal". config.py llama a
aplicar(): la variable DATABASE_URL queda apuntando a la base activa, asi todas las tareas la usan.
"""
import os
import time

import psycopg2

CANDIDATAS = (4, 11)          # numeros de los secretos TEXTOS_URL_<n> que pueden ser la principal
NOMBRE = {4: "A (normas-textos-4)", 11: "B (normas-textos-11)"}
SQL = """CREATE TABLE IF NOT EXISTS principal (
    id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    activa      SMALLINT NOT NULL DEFAULT 4,      -- numero del secreto TEXTOS_URL_<n> en uso
    estado      TEXT NOT NULL DEFAULT 'ok',       -- ok | copiando (mientras se copia a la otra base)
    cambiado_en TIMESTAMPTZ,
    detalle     TEXT)"""

_cache = {"t": 0.0, "fila": None}


def url_de(n):
    return os.getenv(f"TEXTOS_URL_{n}", "").strip()


def control_url():
    return os.getenv(f"TEXTOS_URL_{os.getenv('TEXTOS_CONTROL', '2')}", "").strip()


def leer(estricto=False):
    """(activa, estado) segun la base de control. Si no se puede leer: con estricto=True la tarea se
    detiene (para no escribir en la base equivocada); si no, se supone la A."""
    if time.time() - _cache["t"] < 300 and _cache["fila"]:
        return _cache["fila"]
    fila = None
    url = control_url()
    if url:
        try:
            c = psycopg2.connect(url, connect_timeout=60)
            try:
                with c.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.principal') IS NOT NULL")
                    if cur.fetchone()[0]:
                        cur.execute("SELECT activa, estado FROM principal WHERE id = 1")
                        r = cur.fetchone()
                        fila = (int(r[0]), r[1]) if r and r[0] in CANDIDATAS else (4, "ok")
                    else:
                        fila = (4, "ok")
            finally:
                c.close()
        except psycopg2.Error as e:
            print(f"  (no se pudo leer cual es la base principal activa: {str(e)[:120]})")
    if fila is None:
        if estricto and url:
            print("::warning title=Base principal::No se pudo leer cual es la base principal activa; "
                  "esta tarea se ejecutara en la proxima vuelta.")
            raise SystemExit(0)
        fila = (4, "ok")
    _cache["fila"], _cache["t"] = fila, time.time()
    return fila


def activa():
    return leer()[0]


def copiando():
    """True mientras se copia la base principal a la otra: las tareas esperan a que termine."""
    if leer()[1] == "copiando":
        print("::warning title=Base principal::Se esta copiando la base principal a la otra base; "
              "esta tarea se ejecutara en la proxima vuelta.")
        return True
    return False


def aplicar():
    """Deja DATABASE_URL apuntando a la base activa. Lo llama config.py (todas las tareas)."""
    if not control_url():
        print("::warning title=Base principal::Esta tarea no tiene la base de control (secreto TEXTOS_URL_2) para "
              "saber cual es la base principal activa; no se ejecuta para no usar la base equivocada.")
        raise SystemExit(0)
    n = leer(estricto=True)[0]
    url = url_de(n) or (os.getenv("DATABASE_URL", "").strip() if n == 4 else "")
    if not url:
        print(f"::warning title=Base principal::La base principal activa es la {NOMBRE[n]} pero esta tarea no "
              f"tiene su cadena de conexion (secreto TEXTOS_URL_{n}); no se ejecuta para no usar la base equivocada.")
        raise SystemExit(0)
    os.environ["DATABASE_URL"] = url
    return url
