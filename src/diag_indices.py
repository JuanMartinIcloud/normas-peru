"""Diagnostico temporal: resultado del vinculo proposicion -> ley y de la revision de leyes."""
import json, os
import psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(s, a=None): cur.execute(s, a); return cur.fetchall()
print("PROYECTOS 00098 y 00013:")
for r in q("""SELECT numero, estado, ley_tipo, ley_numero, ley_fecha, ley_docs, enlace_id, enlace_numero, enlace_camara, enlace_estado
              FROM proyectos_ley WHERE numero IN ('00098-2026-2031-CD', '00013-2026-2031-S')"""):
    print(" ", r)
print("Convertidas en ley:", q("""SELECT periodo, count(*), count(*) FILTER (WHERE ley_docs->'ley' IS NOT NULL) FROM proyectos_ley
                                 WHERE ley_numero IS NOT NULL GROUP BY 1"""))
print("Publicadas sin numero:", q("SELECT periodo, count(*) FROM proyectos_ley WHERE estado ILIKE 'publicad%%' AND ley_numero IS NULL GROUP BY 1"))
print("Enlazadas entre camaras:", q("SELECT count(*) FROM proyectos_ley WHERE enlace_id IS NOT NULL"))
ids = json.loads((q("SELECT valor FROM configuracion WHERE clave = 'revision_leyes'") or [["[]"]])[0][0])
print("\nREVISION DE LEYES:", len(ids))
for r in q("""SELECT n.fecha, n.tipo, n.numero, left(n.sumilla, 100), a.relevante, a.calificacion, a.puntaje, a.impacto
              FROM normas n LEFT JOIN analisis a ON a.tipo='N' AND a.ref_id=n.id WHERE n.id = ANY(%s)
              ORDER BY a.relevante DESC NULLS LAST, n.fecha DESC""", (ids,)):
    print(" ", r)
