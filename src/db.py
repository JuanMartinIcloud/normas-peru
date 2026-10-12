"""Acceso a Neon (PostgreSQL)."""
import psycopg2
from psycopg2.extras import execute_values

import config


def conectar():
    if not config.DATABASE_URL:
        raise SystemExit("Falta la variable de entorno DATABASE_URL (cadena de conexion de Neon).")
    return psycopg2.connect(config.DATABASE_URL)


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
    """Inserta proyectos de ley; si ya existen, actualiza su estado y datos."""
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
                    estado = EXCLUDED.estado, titulo = EXCLUDED.titulo, autor = EXCLUDED.autor,
                    proponente = EXCLUDED.proponente, rubro = EXCLUDED.rubro,
                    fecha_presentacion = EXCLUDED.fecha_presentacion, actualizado = now()""",
            valores,
        )
    conn.commit()
    return len(filas)
