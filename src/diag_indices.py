"""Diagnostico temporal: proyecto de delegacion de facultades y la ley publicada."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(s, a=None): cur.execute(s, a); return cur.fetchall()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='proyectos_ley' ORDER BY ordinal_position"); print([r[0] for r in cur.fetchall()])
for r in q("""SELECT id, periodo, camara, numero, num_pley, fecha_presentacion, estado, estado_cambiado_en, actualizado, camara_actual, proponente, left(titulo,150)
              FROM proyectos_ley WHERE numero ILIKE '00098-2026%' OR titulo ILIKE '%delega%facultad%' AND fecha_presentacion >= '2026-07-01'"""):
    print("\nPROY", r)
    for s in q("SELECT fecha, camara, estado, left(comisiones,60), left(detalle,140) FROM seguimientos WHERE proyecto_id = %s ORDER BY fecha", (r[0],)):
        print("   seg", s)
    print("   analisis", q("SELECT relevante, calificacion, puntaje, fecha, criterio FROM analisis WHERE tipo='P' AND ref_id=%s", (r[0],)))
print("\nNORMAS:")
for r in q("""SELECT n.id, n.fecha, n.tipo, n.numero, n.entidad, left(n.sumilla,160), a.relevante, a.puntaje
              FROM normas n LEFT JOIN analisis a ON a.tipo='N' AND a.ref_id=n.id
              WHERE n.fecha >= '2026-10-01' AND (n.sumilla ILIKE '%delega%facultad%' OR (n.tipo ILIKE 'ley%' ) OR n.tipo ILIKE '%errata%ley%')
              ORDER BY n.fecha"""):
    print(r)
print("\nultima actualizacion congreso:", q("SELECT max(actualizado), max(estado_cambiado_en) FROM proyectos_ley"))
