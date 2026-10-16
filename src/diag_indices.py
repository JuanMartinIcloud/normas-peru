import requests, re
A = {"User-Agent": "Mozilla/5.0"}
for n in ("30440", "30441", "30474", "31638", "31477", "30532"):
    for per in ("2016_2021", "2011_2016", "2021_2026"):
        u = f"https://leyes.congreso.gob.pe/Documentos/{per}/ADLP/Normas_Legales/{n}-LEY.pdf"
        r = requests.get(u, headers=A, timeout=40)
        if r.status_code == 200: print("OK", u, len(r.content))
    r = requests.get(f"https://leyes.congreso.gob.pe/LeyNume_1p.aspx?xEstado=2&xTipoNorma=0&xTipoBusqueda=4&xFechaI=&xFechaF=&xTexto=&ordenPor=0&xNormaI={n}&xNormaF={n}", headers=A, timeout=40)
    links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', r.text)
    print(n, [l for l in links if re.search(r"(?i)pdf|Documentos|Ley", l)][:8])
