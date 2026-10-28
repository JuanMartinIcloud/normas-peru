"""Revision unica de las normas con rango de ley (leyes, decretos legislativos y de urgencia, resoluciones
legislativas) y sus fe de erratas que el filtro rapido descarto antes de que existiera la segunda revision
(por ejemplo, la Ley 32743, que delega facultades al Poder Ejecutivo).

    python src/revisar_leyes.py --max-minutos 100

1. (Una sola vez) borra esos descartes y guarda la lista en configuracion ("revision_leyes").
2. Las vuelve a pasar por el filtro, con la segunda revision, y por el analisis las que correspondan.
   Si el tiempo no alcanza, la siguiente ejecucion sigue con las que falten.
"""
import argparse
import json

import db
import gemini
from monitoreo import Reloj, consultar, escribir_config, leer_config, procesar_normas

TIPOS = r"^\s*(fe\s+de\s+erratas?\s+)?(ley|decreto\s+legislativo|decreto\s+de\s+urgencia|resoluci[oó]n\s+legislativa)\M"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutos", type=float, default=100)
    a = ap.parse_args()
    reloj = Reloj(a.max_minutos)
    gemini.verificar_clave()
    db.conectar().close()
    guardado = leer_config("revision_leyes")
    if guardado is None:
        c = db.conectar()
        with c.cursor() as cur:
            cur.execute(
                """DELETE FROM analisis a USING normas n
                   WHERE a.tipo = 'N' AND a.ref_id = n.id AND NOT a.relevante AND a.resumen IS NULL AND NOT a.excluido
                     AND n.tipo ~* %s
                   RETURNING n.id""", (TIPOS,))
            ids = sorted(r[0] for r in cur.fetchall())
        c.commit()
        c.close()
        escribir_config("revision_leyes", json.dumps(ids))
        print(f"Descartes borrados para revisar de nuevo: {len(ids)}")
    else:
        ids = json.loads(guardado)
    if not ids:
        return
    pendientes = consultar("""SELECT min(n.fecha), max(n.fecha), count(*) FROM normas n
                              WHERE n.id = ANY(%s) AND NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'N' AND a.ref_id = n.id)""",
                           (ids,))[0]
    print(f"Normas con rango de ley por revisar: {pendientes[2]} de {len(ids)}")
    if pendientes[2]:
        hechas, completo = procesar_normas(pendientes[0], pendientes[1], reloj, ids=ids)
        print(f"Analizadas en esta ejecucion: {hechas}; completo={completo}")
    r = consultar("""SELECT count(*) FILTER (WHERE a.relevante), count(a.id), count(*)
                     FROM normas n LEFT JOIN analisis a ON a.tipo = 'N' AND a.ref_id = n.id WHERE n.id = ANY(%s)""", (ids,))[0]
    print(f"Resultado: {r[0]} ahora en el reporte, {r[1]} revisadas de {r[2]}")
    for f in consultar("""SELECT n.fecha, n.tipo, n.numero, left(n.sumilla, 110), a.calificacion, a.puntaje
                          FROM normas n JOIN analisis a ON a.tipo = 'N' AND a.ref_id = n.id
                          WHERE n.id = ANY(%s) AND a.relevante ORDER BY n.fecha DESC LIMIT 80""", (ids,)):
        print("  ", f)


if __name__ == "__main__":
    main()
