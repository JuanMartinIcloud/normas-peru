"""Descarga las normas de hoy (o de una fecha) y las guarda en Neon.

    python src/run_dia.py                 # hoy (hora de Lima)
    python src/run_dia.py 2026-10-09      # una fecha
    python src/run_dia.py --sin-bd        # solo muestra lo descargado, no escribe en la base
"""
import sys
from datetime import date, datetime, timedelta, timezone

import db
import elperuano


def hoy_lima() -> date:
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sin_bd = "--sin-bd" in sys.argv
    fecha = date.fromisoformat(args[0]) if args else hoy_lima()

    filas = elperuano.descargar_dia(fecha)
    print(f"{fecha}: {len(filas)} normas encontradas")

    if sin_bd:
        for f in filas[:10]:
            print(f"  [{f['sector']} / {f['rubro']}] {f['tipo']} {f['numero']} - {(f['sumilla'] or '')[:90]}")
        return

    conn = db.conectar()
    try:
        nuevas = db.insertar_normas(conn, filas)
        db.marcar_dia(conn, fecha, "ok" if filas else "vacio", len(filas))
        print(f"{nuevas} nuevas guardadas en la base")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
