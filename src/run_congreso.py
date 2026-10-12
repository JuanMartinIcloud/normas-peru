"""Descarga todos los proyectos de ley del portal del Congreso y los guarda en Neon.

    python src/run_congreso.py             # todos los periodos disponibles
    python src/run_congreso.py --sin-bd    # solo cuenta, no escribe
"""
import sys

import congreso
import db


def main():
    sin_bd = "--sin-bd" in sys.argv
    conn = None if sin_bd else db.conectar()
    total_guardados = 0
    try:
        for per in congreso.periodos():
            for camara in congreso.CAMARAS:
                vistos = 0
                for lote, total in congreso.paginas(per["perParId"], camara):
                    filas = [congreso.normalizar(p, camara) for p in lote]
                    vistos += len(filas)
                    if conn:
                        total_guardados += db.upsert_proyectos(conn, filas)
                if vistos:
                    print(f"periodo {per['desPerParAbrev']} camara {camara}: {vistos} proyectos")
    finally:
        if conn:
            conn.close()
    print(f"Total guardados/actualizados: {total_guardados}")


if __name__ == "__main__":
    main()
