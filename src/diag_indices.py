"""Diagnostico temporal: vinculo proposicion -> ley y calificacion de leyes publicadas."""
import json, os, sys, time
import psycopg2, requests
sys.path.insert(0, os.path.dirname(__file__))
from textos import API_CONGRESO, CABECERAS_CONGRESO, cifrar

for per, num, cam in (("2026", "13", "S"), ("2026", "98", "D")):
    r = requests.get(f"{API_CONGRESO}/expediente/{cifrar(per)}/{cifrar(num)}", params={"codTipoParl": cam},
                     headers=CABECERAS_CONGRESO, timeout=60)
    d = r.json().get("data") or {}
    print("\n=== EXPEDIENTE", cam, num, list(d.keys()))
    print("general:", json.dumps(d.get("general"), ensure_ascii=False)[:4000])
    for k, v in d.items():
        if k not in ("general", "seguimientos"):
            print(k, ":", json.dumps(v, ensure_ascii=False)[:2500])
    segs = d.get("seguimientos") or []
    if segs:
        print("seguimiento ejemplo:", json.dumps(segs[-1], ensure_ascii=False)[:1500])
    time.sleep(1)

c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
def q(s, a=None): cur.execute(s, a); return cur.fetchall()
print("\nANALISIS LEY 32743:")
for r in q("""SELECT n.id, n.tipo, a.relevante, a.calificacion, a.puntaje, a.criterio, a.lectura, a.modelo, a.excluido, a.excluido_por,
                     left(a.resumen,400), left(a.comentario,300)
              FROM normas n LEFT JOIN analisis a ON a.tipo='N' AND a.ref_id=n.id WHERE n.numero = '32743'"""):
    print(r)
print("\nLEYES desde julio sin relevancia:")
for r in q("""SELECT n.fecha, n.tipo, n.numero, left(n.sumilla,110), a.relevante, a.puntaje, a.criterio
              FROM normas n LEFT JOIN analisis a ON a.tipo='N' AND a.ref_id=n.id
              WHERE n.fecha >= '2026-07-01' AND n.entidad ILIKE 'CONGRESO%' ORDER BY n.fecha"""):
    print(r)
print("\nSeguimientos 'Publicada':", q("SELECT count(*), count(DISTINCT proyecto_id) FROM seguimientos WHERE estado ILIKE 'publicad%'"))
for r in q("""SELECT p.periodo, p.camara, p.numero, s.fecha::date, left(s.detalle,120) FROM seguimientos s JOIN proyectos_ley p ON p.id=s.proyecto_id
              WHERE s.estado ILIKE 'publicad%' ORDER BY s.fecha DESC LIMIT 25"""):
    print("  ", r)
print("\nPeriodos y camaras:", q("SELECT periodo, camara, count(*) FROM proyectos_ley GROUP BY 1,2 ORDER BY 1,2"))
print("Estados con 'Publicad' en proyectos:", q("SELECT periodo, count(*) FROM proyectos_ley WHERE estado ILIKE 'publicad%' GROUP BY 1"))
print("Senado remitidas por Diputados:", q("SELECT count(*) FROM proyectos_ley WHERE camara='S' AND titulo ILIKE 'PROPUESTA LEGISLATIVA REMITIDA%'"))
for r in q("SELECT numero, left(titulo,200), proponente, autor FROM proyectos_ley WHERE camara='S' AND titulo ILIKE 'PROPUESTA LEGISLATIVA REMITIDA%' LIMIT 8"):
    print("  ", r)
print("Diputados remitidas al Senado:", q("SELECT count(*) FROM proyectos_ley WHERE camara='D' AND estado ILIKE '%remitida al senado%'"))
