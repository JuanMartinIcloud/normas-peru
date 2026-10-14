import os, sys, psycopg2, requests
sys.path.insert(0, "src")
import indexar
t3 = psycopg2.connect(os.environ["TEXTOS_URL_3"]); c3 = t3.cursor()
c3.execute("SELECT clave FROM documentos WHERE tipo='N' AND estado='sin_pdf' ORDER BY random() LIMIT 8")
claves = [r[0] for r in c3.fetchall()]
m = psycopg2.connect(os.environ["DATABASE_URL"]); cm = m.cursor()
cm.execute("SELECT hash_unico, fecha, url_detalle, url_pdf, tipo, numero FROM normas WHERE hash_unico = ANY(%s)", (claves,))
for h, fecha, det, pdf, tipo, num in cm.fetchall():
    print("----", fecha, tipo, num)
    print("  url_detalle:", det)
    print("  url_pdf:", pdf)
    import re, base64
    mm = re.search(r"/dispositivo/[A-Z]+/(\d+-\d+)", det or "")
    print("  codigo:", mm.group(1) if mm else None)
    try:
        r = indexar.pedir(indexar.EPDOC, params={"Referencias": base64.b64encode(f"{mm.group(1)}{fecha.strftime('%Y%m%d')}".encode()).decode()}, headers={"User-Agent": indexar.AGENTE}) if mm else None
        if r is not None:
            print("  epdoc:", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:60])
    except Exception as e:
        print("  epdoc ERROR", e)
    if pdf:
        try:
            r = requests.get(pdf, timeout=60, headers={"User-Agent": indexar.AGENTE})
            print("  url_pdf:", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:20])
        except Exception as e:
            print("  url_pdf ERROR", e)
c3.execute("SELECT count(*) FROM documentos WHERE estado='sin_pdf'")
print("sin_pdf en base 3:", c3.fetchone())
