import os, sys, base64, re
import psycopg2, requests
sys.path.insert(0, "src")
from indexar import EPDOC, AGENTE
m = psycopg2.connect(os.environ["DATABASE_URL"]); cm = m.cursor()
cm.execute("""SELECT url_detalle LIKE '%%/dispositivo/%%' AS nuevo, extract(year from fecha)::int, count(*)
              FROM normas GROUP BY 1, 2 ORDER BY 2, 1""")
for r in cm.fetchall(): print("formato", r)
cm.execute("""SELECT fecha, url_detalle FROM normas WHERE url_detalle NOT LIKE '%%/dispositivo/%%'
              ORDER BY random() LIMIT 6""")
for fecha, det in cm.fetchall():
    mm = re.search(r"-(\d+-\d+)/?$", det or "")
    cod = mm.group(1) if mm else None
    print("----", fecha, det[-60:], "codigo:", cod)
    if cod:
        ref = base64.b64encode(f"{cod}{fecha.strftime('%Y%m%d')}".encode()).decode()
        r = requests.get(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE}, timeout=60)
        print("epdoc:", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:8])
cm.execute("SELECT count(*) FROM normas WHERE url_detalle NOT LIKE '%%/dispositivo/%%' AND url_detalle !~ '-[0-9]+-[0-9]+/?$'")
print("sin codigo reconocible:", cm.fetchone())
