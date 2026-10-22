"""Diagnostico temporal: estado de la recalificacion y ejemplos del usuario."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(s): cur.execute(s); return cur.fetchall()
print("criterio actual:", q("SELECT max(criterio) FROM analisis"))
print("pendientes:", q("SELECT count(*) FROM analisis WHERE relevante AND criterio IS DISTINCT FROM (SELECT max(criterio) FROM analisis)"))
print("por mes:", q("SELECT to_char(fecha,'YYYY-MM'), count(*) FILTER (WHERE relevante), count(*) FILTER (WHERE relevante AND puntaje IS NULL) FROM analisis GROUP BY 1 ORDER BY 1"))
for t in ("%021-2026-EM%", "%397-2026-VIVIENDA%", "%2860%", "%000125-2026-CD/OSIPTEL%", "%300-2026-PCM%"):
    print(t, q(f"""SELECT n.tipo, n.numero, a.relevante, a.calificacion, a.puntaje, a.criterio FROM analisis a JOIN normas n ON n.id = a.ref_id AND a.tipo='N'
                   WHERE n.numero ILIKE '{t}' AND n.fecha >= '2026-09-01'"""))
