"""Diagnostico temporal: norma de la SMV sobre el Codigo de Buen Gobierno Corporativo."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("""SELECT n.id, n.fecha, n.tipo, n.numero, n.entidad, n.sector, left(n.sumilla, 300), n.url_detalle,
                      a.relevante, a.calificacion, a.puntaje, a.impacto, a.criterio, a.excluido, a.creado_en, left(a.resumen, 200)
               FROM normas n LEFT JOIN analisis a ON a.tipo = 'N' AND a.ref_id = n.id
               WHERE (n.sumilla ILIKE '%gobierno corporativo%' OR n.sumilla ILIKE '%buen gobierno%')
                 AND n.fecha >= '2026-09-01' ORDER BY n.fecha DESC""")
for r in cur.fetchall(): print(r, "\n")
cur.execute("""SELECT n.fecha, n.tipo, n.numero, left(n.sumilla, 160), a.relevante FROM normas n
               LEFT JOIN analisis a ON a.tipo = 'N' AND a.ref_id = n.id
               WHERE n.entidad ILIKE '%mercado de valores%' AND n.fecha >= '2026-10-01' ORDER BY n.fecha DESC""")
for r in cur.fetchall(): print("SMV:", r)
cur.execute("SELECT max(fecha) FROM normas"); print("ultima norma:", cur.fetchone())
