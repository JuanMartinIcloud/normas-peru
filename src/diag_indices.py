"""Diagnostico temporal: resumenes, monitoreo, informes, busquedas guardadas."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(sql):
    cur.execute(sql); return cur.fetchall()
print("resumenes:", q("SELECT fecha, modelo, n_normas, n_proyectos, n_cambios, creado_en FROM resumenes ORDER BY fecha DESC LIMIT 5"))
print("analisis por fecha (ultimos 7 dias):", q("SELECT tipo, fecha, count(*), sum(relevante::int) FROM analisis WHERE fecha >= current_date - 7 GROUP BY 1, 2 ORDER BY 2, 1"))
print("normas sin analisis (ultimos 30 dias):", q("""SELECT count(*) FROM normas n WHERE n.fecha >= current_date - 30 AND n.fecha < current_date
     AND NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'N' AND a.ref_id = n.id)"""))
print("analisis por mes:", q("SELECT to_char(fecha, 'YYYY-MM'), count(*) FROM analisis GROUP BY 1 ORDER BY 1"))
print("informes:", q("SELECT fecha, estado, aprobado_por, enviado_en, ejecutivo IS NOT NULL, actualizado FROM informes ORDER BY fecha DESC LIMIT 5"))
print("busquedas:", q("SELECT id, nombre, frecuencia, activa, ultima_ejecucion FROM busquedas_guardadas"))
print("ejecuciones:", q("SELECT busqueda_id, desde, hasta, total_normas, total_proyectos, resumen IS NOT NULL, creado_en FROM busqueda_ejecuciones ORDER BY creado_en DESC LIMIT 6"))
print("config:", q("SELECT * FROM config") if q("SELECT to_regclass('public.config')")[0][0] else "-")
print("usuarios:", q("SELECT usuario, rol, activo FROM usuarios"))
