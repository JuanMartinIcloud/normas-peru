"""Informe del estado de la base. Escribe avisos (::notice::) que se pueden leer desde la API de GitHub."""
import db


def aviso(titulo, texto):
    texto = str(texto).replace("\n", " | ")
    print(f"::notice title={titulo}::{texto}")
    print(f"{titulo}: {texto}")


def main():
    conn = db.conectar()
    cur = conn.cursor()

    cur.execute("SELECT count(*), min(fecha), max(fecha) FROM normas")
    total, primera, ultima = cur.fetchone()
    aviso("normas_total", f"{total} normas, de {primera} a {ultima}")

    cur.execute("SELECT extract(year FROM fecha)::int, count(*) FROM normas GROUP BY 1 ORDER BY 1")
    aviso("normas_por_anio", "; ".join(f"{a}:{n}" for a, n in cur.fetchall()))

    cur.execute("SELECT estado, count(*) FROM descargas GROUP BY 1 ORDER BY 1")
    aviso("dias_por_estado", "; ".join(f"{e}:{n}" for e, n in cur.fetchall()))

    cur.execute("SELECT min(fecha), max(fecha), count(*) FROM descargas")
    a, b, c = cur.fetchone()
    aviso("dias_cubiertos", f"{c} dias registrados, de {a} a {b}")

    cur.execute("SELECT fecha, left(detalle, 80) FROM descargas WHERE estado='error' ORDER BY fecha DESC LIMIT 15")
    errores = cur.fetchall()
    aviso("dias_con_error", "; ".join(f"{f}:{d}" for f, d in errores) or "ninguno")

    cur.execute(
        """SELECT extract(year FROM fecha)::int, count(*) FROM descargas
           WHERE estado='vacio' GROUP BY 1 ORDER BY 1"""
    )
    aviso("dias_vacios_por_anio", "; ".join(f"{a}:{n}" for a, n in cur.fetchall()) or "ninguno")

    cur.execute("SELECT sector, count(*) FROM normas GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
    aviso("sectores_top", "; ".join(f"{s}:{n}" for s, n in cur.fetchall()))

    cur.execute("SELECT rubro, count(*) FROM normas GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
    aviso("rubros_top", "; ".join(f"{s}:{n}" for s, n in cur.fetchall()))

    cur.execute("SELECT count(*) FROM proyectos_ley")
    aviso("proyectos_ley_total", cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
