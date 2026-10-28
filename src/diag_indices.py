"""Diagnostico temporal: rehace el analisis de las proposiciones recien convertidas en ley."""
import os
import psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cur.execute("""DELETE FROM analisis a USING proyectos_ley p WHERE a.tipo='P' AND a.ref_id=p.id
               AND p.numero IN ('00098-2026-2031-CD', '00013-2026-2031-S')""")
print("borrados", cur.rowcount); c.commit()
