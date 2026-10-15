"""Diagnostico temporal: reporte del Congreso de un dia y cuota de cada modelo de IA."""
import os, psycopg2, requests
db = psycopg2.connect(os.environ["DATABASE_URL"]); cur = db.cursor()
for d in ("2026-10-13", "2026-10-14"):
    q = {
     "dip_ingresadas": "SELECT count(*) FROM proyectos_ley p WHERE camara='D' AND fecha_presentacion=%s",
     "sen_ingresadas": "SELECT count(*) FROM proyectos_ley p WHERE camara='S' AND fecha_presentacion=%s",
     "dictamenes": "SELECT count(DISTINCT proyecto_id) FROM seguimientos s WHERE estado ILIKE '%%dictamen%%' AND (fecha AT TIME ZONE 'America/Lima')::date=%s",
     "autografas": "SELECT count(DISTINCT proyecto_id) FROM seguimientos s WHERE estado ILIKE '%%aut_grafa%%' AND (fecha AT TIME ZONE 'America/Lima')::date=%s",
     "seguimientos_dia": "SELECT count(*) FROM seguimientos s WHERE (fecha AT TIME ZONE 'America/Lima')::date=%s",
    }
    for k, s in q.items():
        cur.execute(s, (d,)); print(d, k, cur.fetchone()[0])
    cur.execute("""SELECT count(*) FILTER (WHERE a.id IS NULL), count(*) FILTER (WHERE a.relevante), count(*) FILTER (WHERE a.relevante=false)
      FROM (SELECT id pid FROM proyectos_ley WHERE fecha_presentacion=%s UNION SELECT proyecto_id FROM seguimientos WHERE (fecha AT TIME ZONE 'America/Lima')::date=%s) b
      LEFT JOIN analisis a ON a.tipo='P' AND a.ref_id=b.pid""", (d, d))
    print(d, "pendientes/relevantes/no_relevantes", cur.fetchone())
cur.execute("SELECT max(fecha), count(*) FROM seguimientos"); print("seguimientos max", cur.fetchone())
cur.execute("SELECT max(fecha_presentacion) FROM proyectos_ley"); print("proyectos max", cur.fetchone())
cur.execute("SELECT clave, valor FROM configuracion WHERE clave LIKE 'historico%%'"); print(cur.fetchall())
cur.execute("SELECT to_char(fecha,'YYYY-MM'), count(*), count(*) FILTER (WHERE relevante) FROM analisis WHERE tipo='N' AND fecha>='2026-08-01' GROUP BY 1 ORDER BY 1"); print("analisis normas", cur.fetchall())
cur.execute("SELECT to_char(fecha,'YYYY-MM'), count(*) FROM normas WHERE fecha>='2026-08-01' GROUP BY 1 ORDER BY 1"); print("normas", cur.fetchall())
k = os.environ["GEMINI_API_KEY"]
for m in ["gemini-flash-latest","gemini-3.5-flash-lite","gemini-2.5-flash","gemini-3.5-flash","gemini-flash-lite-latest","gemini-3.1-flash-lite","gemini-2.5-flash-lite","gemini-3.1-flash-lite-preview","gemini-3.8-flash","gemini-3.7-flash","gemini-3.6-flash","gemini-3-flash-preview","gemma-4-31b-it"]:
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": k},
                      json={"contents":[{"parts":[{"text":"di ok"}]}]}, timeout=90)
    print("modelo", m, r.status_code, r.text[:120].replace("\n"," ") if r.status_code!=200 else "")
