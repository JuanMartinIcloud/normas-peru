"""Diagnostico temporal: como arma El Peruano el enlace del cuadernillo (chunks de Next.js)."""
import re, requests
A = {"User-Agent": "Mozilla/5.0"}
B = "https://busquedas.elperuano.pe"
u = B + "/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"
h = requests.get(u, headers=A, timeout=60).text
chunks = sorted(set(re.findall(r'(/_next/static/[^"\'\s\\]+\.js)', h)))
print(len(chunks), "chunks")
vistos = set()
pend = list(chunks)
while pend:
    c = pend.pop()
    if c in vistos or len(vistos) > 80: continue
    vistos.add(c)
    try: js = requests.get(B + c, headers=A, timeout=60).text
    except Exception: continue
    pend += [x for x in set(re.findall(r'(/_next/static/[^"\'\s\\]+\.js)', js)) if x not in vistos]
    for pat in (r"(?i)cuadernillo", r"(?i)DescargaIN|VistaDE|epdoc", r"(?i)/api/[a-z/]+", r"(?i)https?://[a-z0-9.\-]+elperuano[^\"'`\s]*"):
        for m in list(re.finditer(pat, js))[:4]:
            print(f"[{c[-30:]}] {pat[:14]}:", js[max(0, m.start() - 150): m.start() + 250].replace("\n", " "))
# datos de la norma en el HTML (Next.js RSC)
for pat in (r'NL2017\d+', r'(?i)\\"[a-z_]*(pdf|cuadern|edicion|url)[a-z_]*\\":\\"[^\\]{0,160}'):
    for m in list(re.finditer(pat, h))[:8]:
        print("H", m.group(0)[:220])
