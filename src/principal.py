"""Registro de las bases de datos del sistema y base principal activa.

Cada proyecto gratuito de Neon tiene su propio cupo de 5 GB de transferencia al mes (y 1 GB de espacio).
Por eso el sistema reparte el trabajo en varias bases:

- Bases PRINCIPALES (normas, proyectos, analisis, usuarios...): hay varias copias posibles y se usa una a
  la vez. Las fijas son TEXTOS_URL_4, 9, 10 y 11; si hacen falta mas, el sistema crea otras solo (13, 14...).
  src/cambiar_principal.py rota entre ellas: cuando la activa gasta 2 GB en el mes, copia todo a la que
  menos gasto y pasa a usarla; cuando todas pasaron los 2 GB, vuelve a rotar hasta unos 3,8 GB cada una.
- Bases de TEXTO (texto completo de normas y proyectos): TEXTOS_URL_2, 3, 5, 6, 7, 8 y 12, mas las que el
  sistema cree solo cuando se queden sin espacio (src/bases_auto.py).
- Base de CONTROL: TEXTOS_URL_2 (tambien es de texto). Guarda cual principal esta activa (tabla
  "principal") y la lista de bases creadas automaticamente (tabla "bases_extra", con su conexion).

config.py llama a aplicar(): la variable DATABASE_URL queda apuntando a la base principal activa.
"""
import os
import time

import psycopg2

FIJAS_PRINCIPALES = (4, 9, 10, 11)
RETIRADAS = (1,)                 # la 1 se copio a la 12 y ya no se usa
SQL = """CREATE TABLE IF NOT EXISTS principal (
    id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    activa      SMALLINT NOT NULL DEFAULT 4,      -- numero de la base (TEXTOS_URL_<n> o bases_extra) en uso
    estado      TEXT NOT NULL DEFAULT 'ok',       -- ok | copiando (mientras se copia a otra base)
    cambiado_en TIMESTAMPTZ,
    detalle     TEXT);
CREATE TABLE IF NOT EXISTS bases_extra (
    numero      SMALLINT PRIMARY KEY,             -- se usa igual que el numero de TEXTOS_URL_<n>
    rol         TEXT NOT NULL,                    -- principal | texto
    url         TEXT NOT NULL,                    -- cadena de conexion
    proyecto    TEXT,                             -- id del proyecto en Neon
    creada      TIMESTAMPTZ NOT NULL DEFAULT now())"""

_cache = {"t": 0.0, "fila": None}
_reg = {"t": 0.0, "filas": None}


def control_url():
    return os.getenv(f"TEXTOS_URL_{os.getenv('TEXTOS_CONTROL', '2')}", "").strip()


def nombre(n):
    return f"base {n}" + (" (normas-textos-%d)" % n if n <= 12 else "")


def _control(sql, args=()):
    c = psycopg2.connect(control_url(), connect_timeout=60)
    try:
        with c.cursor() as cur:
            cur.execute(sql, args)
            filas = cur.fetchall() if cur.description else []
        c.commit()
        return filas
    finally:
        c.close()


def registro():
    """{numero: (rol, url)} de la tabla bases_extra (cache de 5 minutos)."""
    if _reg["filas"] is not None and time.time() - _reg["t"] < 300:
        return _reg["filas"]
    filas = {}
    if control_url():
        try:
            if _control("SELECT to_regclass('public.bases_extra') IS NOT NULL")[0][0]:
                filas = {int(n): (r, u) for n, r, u in _control("SELECT numero, rol, url FROM bases_extra")}
        except psycopg2.Error as e:
            print(f"  (no se pudo leer el registro de bases: {str(e)[:120]})")
            if _reg["filas"] is not None:
                return _reg["filas"]
            filas = None
    if filas is None:
        return {}
    _reg["filas"], _reg["t"] = filas, time.time()
    return filas


def url_de(n):
    """Cadena de conexion de la base n: secreto TEXTOS_URL_<n> o, si no esta, el registro."""
    url = os.getenv(f"TEXTOS_URL_{n}", "").strip()
    if url:
        return url
    r = registro().get(int(n))
    return r[1] if r else ""


def principales():
    """Numeros de las bases que pueden ser la principal (fijas + creadas automaticamente)."""
    return sorted(set(FIJAS_PRINCIPALES) | {n for n, (rol, _) in registro().items() if rol == "principal"})


def bases_texto():
    """[(numero, url)] de las bases de texto (secretos 1..12 que no son principales ni retiradas + registro)."""
    salida = []
    for i in range(1, 13):
        if i in FIJAS_PRINCIPALES or (i in RETIRADAS and os.getenv("TEXTOS_URL_12", "").strip()):
            continue
        url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
        if url:
            salida.append((i, url))
    for n, (rol, url) in sorted(registro().items()):
        if rol == "texto":
            salida.append((n, url))
    return salida


def leer(estricto=False):
    """(activa, estado) segun la base de control. Si no se puede leer: con estricto=True la tarea se
    detiene (para no escribir en la base equivocada); si no, se supone la 4."""
    if time.time() - _cache["t"] < 300 and _cache["fila"]:
        return _cache["fila"]
    fila = None
    if control_url():
        try:
            if _control("SELECT to_regclass('public.principal') IS NOT NULL")[0][0]:
                r = _control("SELECT activa, estado FROM principal WHERE id = 1")
                fila = (int(r[0][0]), r[0][1]) if r else (4, "ok")
            else:
                fila = (4, "ok")
        except psycopg2.Error as e:
            print(f"  (no se pudo leer cual es la base principal activa: {str(e)[:120]})")
    if fila is None:
        if estricto and control_url():
            print("::warning title=Base principal::No se pudo leer cual es la base principal activa; "
                  "esta tarea se ejecutara en la proxima vuelta.")
            raise SystemExit(0)
        fila = (4, "ok")
    _cache["fila"], _cache["t"] = fila, time.time()
    return fila


def activa():
    return leer()[0]


def copiando():
    """True mientras se copia la base principal a otra: las tareas esperan a que termine."""
    if leer()[1] == "copiando":
        print("::warning title=Base principal::Se esta copiando la base principal a otra base; "
              "esta tarea se ejecutara en la proxima vuelta.")
        return True
    return False


def aplicar():
    """Deja DATABASE_URL apuntando a la base principal activa. Lo llama config.py (todas las tareas)."""
    if not control_url():
        print("::warning title=Base principal::Esta tarea no tiene la base de control (secreto TEXTOS_URL_2) para "
              "saber cual es la base principal activa; no se ejecuta para no usar la base equivocada.")
        raise SystemExit(0)
    n = leer(estricto=True)[0]
    url = url_de(n) or (os.getenv("DATABASE_URL", "").strip() if n == 4 else "")
    if not url:
        print(f"::warning title=Base principal::La base principal activa es la {nombre(n)} pero esta tarea no "
              f"tiene su cadena de conexion; no se ejecuta para no usar la base equivocada.")
        raise SystemExit(0)
    os.environ["DATABASE_URL"] = url
    return url
