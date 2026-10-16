import re, requests
A = {"User-Agent": "Mozilla/5.0"}
B = "https://busquedas.elperuano.pe"
u = B + "/dispositivo/NL/1582046-1"
h = requests.get(u, headers=A, timeout=60).text
assets = sorted(set(re.findall(r'"(/assets/[^"]+\.js)"', h)))
vistos, pend = set(), list(assets)
while pend:
    c = pend.pop()
    if c in vistos or len(vistos) > 60: continue
    vistos.add(c)
    js = requests.get(B + c, headers=A, timeout=60).text
    pend += [("/assets/" + x.split("/")[-1]) for x in set(re.findall(r'["\'(]\.?\.?/?(?:assets/)?([A-Za-z0-9_.()\-]+\.js)["\']', js))]
    for pat in (r"(?i)cuadernillo", r"(?i)epdoc|DescargaIN|VistaDE", r"https?://[a-z0-9.\-]*elperuano\.pe[^\"'`\s]*"):
        for m in list(re.finditer(pat, js))[:5]:
            print(f"[{c}] {pat[:12]}:", js[max(0, m.start() - 250): m.start() + 250].replace("\n", " "))
# datos embebidos
for pat in (r'(?i)cuadernillo[^<]{0,200}', r'(?i)"(?:urlPdf|pdf|archivo|cuadernillo|edicion)[A-Za-z]*"\s*:\s*"[^"]{0,200}"', r'window\.__[A-Za-z_]+\s*=\s*.{0,1500}'):
    for m in list(re.finditer(pat, h))[:6]:
        print("H", m.group(0)[:600])
