"""Diagnostico temporal: normas que siguen sin texto."""
import os, sys, re, random
sys.path.insert(0, os.path.dirname(__file__))
from indexar import Bases, principal, BUSQUEDAS, AGENTE, _paginas_pdf
import requests
b = Bases()
print("Revisados:", b.ejecutar(b.control, lambda cur: (cur.execute("SELECT tipo, resultado, count(*) FROM ocr_revisado GROUP BY 1, 2 ORDER BY 1, 2"), cur.fetchall())[1]))
claves = []
for url in b.urls:
    claves += b.ejecutar(url, lambda cur: (cur.execute("SELECT clave FROM documentos WHERE tipo='N' AND estado <> 'ok'"), [r[0] for r in cur.fetchall()])[1])
c = principal(); cur = c.cursor()
cur.execute("""SELECT fecha, tipo, numero, entidad, extraordinaria, url_detalle, left(sumilla, 90) FROM normas
               WHERE hash_unico = ANY(%s) ORDER BY fecha""", (claves,))
filas = cur.fetchall()
print(len(filas), "sin texto")
por = {}
for f in filas: por[f[0].year] = por.get(f[0].year, 0) + 1
print(sorted(por.items()))
print("extraordinarias:", sum(1 for f in filas if f[4]))
from collections import Counter
print(Counter(f[1] for f in filas).most_common(12))
random.seed(5)
for f in random.sample(filas, 6):
    print("\n", f)
    clave = f[0].strftime("%Y%m%d")
    r = requests.get(f"{BUSQUEDAS}/cuadernillo/NL/{clave}", headers={"User-Agent": AGENTE}, timeout=60)
    rutas = list(dict.fromkeys(re.findall(r'(/api/archivo/file/[^"\\]+\.pdf)', r.text)))
    print("  cuadernillo", r.status_code, rutas[:6])
    for ruta in [x for x in rutas if "NL" + clave in x][:2]:
        rp = requests.get(BUSQUEDAS + ruta, headers={"User-Agent": AGENTE}, timeout=180)
        pags = _paginas_pdf(rp.content) if rp.content[:4] == b"%PDF" else []
        num = re.sub(r"\s+", "", str(f[2] or ""))
        nums = re.findall(r"\d{2,}", num)
        hits = [i for i, p in enumerate(pags) if nums and all(n in p for n in nums)]
        print("  ", ruta[-30:], len(rp.content), "paginas", len(pags), "texto", sum(map(len, pags)), "paginas con los numeros", hits[:8])
