"""Diagnostico temporal: avance de la recalificacion del monitoreo."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(s): cur.execute(s); return cur.fetchall()
print("columnas:", q("SELECT column_name FROM information_schema.columns WHERE table_name='analisis' AND column_name IN ('puntaje','criterio')"))
print("pendientes:", q("SELECT count(*) FROM analisis WHERE relevante AND criterio IS DISTINCT FROM 3"))
print("recalificados:", q("SELECT relevante, calificacion, count(*) FROM analisis WHERE criterio = 3 GROUP BY 1, 2 ORDER BY 1, 2"))
print("puntajes:", q("SELECT puntaje, count(*) FROM analisis WHERE criterio = 3 AND relevante GROUP BY 1 ORDER BY 1"))
for t in ("Decreto Supremo%021-2026-EM%", "%397-2026-VIVIENDA%", "%2860%"):
    print(t, q(f"""SELECT n.tipo, n.numero, a.relevante, a.calificacion, a.puntaje, a.criterio FROM analisis a JOIN normas n ON n.id = a.ref_id AND a.tipo='N'
                   WHERE (n.tipo || ' ' || n.numero) ILIKE '{t}' AND n.fecha >= '2026-10-01'"""))
print("muestra:", q("""SELECT coalesce(n.tipo||' '||n.numero, 'Proy '||p.numero), a.relevante, a.calificacion, a.puntaje, left(coalesce(n.sumilla, p.titulo), 90)
   FROM analisis a LEFT JOIN normas n ON a.tipo='N' AND n.id=a.ref_id LEFT JOIN proyectos_ley p ON a.tipo='P' AND p.id=a.ref_id
   WHERE a.criterio = 3 ORDER BY random() LIMIT 25"""))
