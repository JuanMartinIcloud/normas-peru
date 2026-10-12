"""Acceso a Neon (PostgreSQL)."""
import os

import psycopg2
from psycopg2.extras import execute_values

import config

_ESQUEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schema.sql")
_MARCA_ETAPA3 = "-- Etapa 3:"


def conectar():
    if not config.DATABASE_URL:
        raise SystemExit("Falta la variable de entorno DATABASE_URL (cadena de conexion de Neon).")
    conn = psycopg2.connect(config.DATABASE_URL)
    asegurar_esquema(conn)
    return conn


def asegurar_esquema(conn):
    """Aplica una sola vez los cambios de la etapa 3 (resumenes con IA).

    Solo actua si falta la tabla 'resumenes' o la columna 'estado_cambiado_en';
    en las ejecuciones siguientes no hace nada.
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                 EXISTS (SELECT 1 FROM information_schema.tables
                         WHERE table_schema = 'public' AND table_name = 'resumenes'),
                 EXISTS (SELECT 1 FROM information_schema.columns
                         WHERE table_schema = 'public' AND table_name = 'proyectos_ley'
                           AND column_name = 'estado_cambiado_en')"""
        )
        tiene_resumenes, tiene_columna = cur.fetchone()
    conn.commit()
    if tiene_resumenes and tiene_columna:
        return
    with open(_ESQUEMA, encoding="utf-8") as f:
        texto = f.read()
    pos = texto.find(_MARCA_ETAPA3)
    if pos < 0:
        raise RuntimeError("No encontre la seccion 'Etapa 3' en schema.sql")
    with conn.cursor() as cur:
        # Candado: si dos tareas arrancan a la vez, la segunda espera a que la primera termine
        cur.execute("SELECT pg_advisory_xact_lock(724501)")
        cur.execute(texto[pos:])
    conn.commit()
    print("Base de datos actualizada para los resumenes diarios.")


def insertar_normas(conn, filas: list[dict]) -> int:
    if not filas:
        return 0
    cols = ["fecha", "tipo", "numero", "entidad", "sector", "rubro",
            "sumilla", "url_pdf", "url_detalle", "extraordinaria", "hash_unico"]
    valores = [[f[c] for c in cols] for f in filas]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO normas ({', '.join(cols)}) VALUES %s ON CONFLICT (hash_unico) DO NOTHING",
            valores,
        )
        n = cur.rowcount
    conn.commit()
    return n


def marcar_dia(conn, fecha, estado: str, cantidad: int = 0, detalle: str = ""):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO descargas (fecha, estado, cantidad, detalle)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (fecha) DO UPDATE
               SET estado = EXCLUDED.estado, cantidad = EXCLUDED.cantidad,
                   detalle = EXCLUDED.detalle, actualizado = now()""",
            (fecha, estado, cantidad, detalle[:500]),
        )
    conn.commit()


def dias_pendientes(conn, desde, hasta) -> list:
    """Fechas del rango que aun no estan en 'ok' o 'vacio' (para reanudar)."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT d::date FROM generate_series(%s::date, %s::date, interval '1 day') d
               WHERE d::date NOT IN (SELECT fecha FROM descargas WHERE estado IN ('ok','vacio'))
               ORDER BY d DESC""",
            (desde, hasta),
        )
        return [r[0] for r in cur.fetchall()]


def upsert_proyectos(conn, filas: list[dict]) -> int:
    """Inserta proyectos de ley; si ya existen, actualiza su estado y datos.

    Si el estado cambia, anota la hora en 'estado_cambiado_en' (lo usa el resumen diario).
    """
    if not filas:
        return 0
    cols = ["periodo", "camara", "numero", "num_pley", "fecha_presentacion",
            "titulo", "autor", "proponente", "estado", "rubro", "url"]
    valores = [[f[c] for c in cols] for f in filas]
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""INSERT INTO proyectos_ley ({', '.join(cols)}) VALUES %s
                ON CONFLICT (periodo, camara, numero) DO UPDATE SET
                    estado_cambiado_en = CASE
                        WHEN EXCLUDED.estado IS NOT NULL
                         AND proyectos_ley.estado IS DISTINCT FROM EXCLUDED.estado THEN now()
                        ELSE proyectos_ley.estado_cambiado_en END,
                    estado = COALESCE(EXCLUDED.estado, proyectos_ley.estado),
                    titulo = EXCLUDED.titulo, autor = EXCLUDED.autor,
                    proponente = EXCLUDED.proponente, rubro = EXCLUDED.rubro,
                    url = COALESCE(EXCLUDED.url, proyectos_ley.url),
                    fecha_presentacion = EXCLUDED.fecha_presentacion, actualizado = now()""",
            valores,
        )
    conn.commit()
    return len(filas)
