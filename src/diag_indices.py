"""Freno manual: la base principal ya paso de 4 GB de transferencia este mes (aviso de Neon del 24 de octubre:
4.2 GB). Sin NEON_API_KEY no hay medicion automatica, asi que se marca a mano hasta fin de mes: se detienen
las tareas no indispensables. La marca vence sola el 1 de noviembre (00:00 de Lima)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import psycopg2
import cupos
c = psycopg2.connect(cupos.control_url()); cur = c.cursor()
cur.execute(cupos.SQL)
url = os.environ["DATABASE_URL"]
cur.execute("""INSERT INTO cupos (host, base, proyecto, transferido, periodo, actualizado)
               VALUES (%s, 'principal', 'normas-textos-4', %s, '2026-10-01', '2026-10-29 05:00+00')
               ON CONFLICT (host) DO UPDATE SET transferido = EXCLUDED.transferido, actualizado = EXCLUDED.actualizado""",
            (cupos.host(url), int(4.2 * 1024 ** 3)))
c.commit()
print("principal_agotada:", cupos.principal_agotada())
m = psycopg2.connect(url); mc = m.cursor()
mc.execute("SELECT count(*) FROM analisis WHERE relevante AND criterio IS DISTINCT FROM (SELECT max(criterio) FROM analisis)")
print("recalificacion pendiente:", mc.fetchone()[0])
