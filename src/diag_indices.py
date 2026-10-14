import os, sys, base64, re
import psycopg2, requests
sys.path.insert(0, "src")
from indexar import pdf_norma, EPDOC, AGENTE
t = psycopg2.connect(os.environ["TEXTOS_URL_3"]); c = t.cursor()
c.execute("SELECT clave FROM documentos WHERE tipo='N' AND estado='sin_pdf' ORDER BY random() LIMIT 6")
claves = [r[0] for r in c.fetchall()]
m = psycopg2.connect(os.environ["DATABASE_URL"]); cm = m.cursor()
cm.execute("SELECT hash_unico, fecha, url_detalle, url_pdf FROM normas WHERE hash_unico = ANY(%s)", (claves,))
for h, fecha, det, pdf in cm.fetchall():
    print("----", fecha, det, pdf)
    mm = re.search(r"/dispositivo/[A-Z]+/(\d+-\d+)", det or "")
    print("codigo:", mm.group(1) if mm else None)
    if mm:
        ref = base64.b64encode(f"{mm.group(1)}{fecha.strftime('%Y%m%d')}".encode()).decode()
        r = requests.get(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE}, timeout=60)
        print("epdoc:", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:80])
    if pdf:
        try:
            r = requests.get(pdf, headers={"User-Agent": AGENTE}, timeout=60)
            print("url_pdf:", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:60])
        except Exception as e:
            print("url_pdf error", e)
