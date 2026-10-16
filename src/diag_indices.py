import requests
A = {"User-Agent": "Mozilla/5.0"}
for n, per in (("30532", "2016_2021"), ("30440", "2011_2016"), ("30474", "2011_2016"), ("30673", "2016_2021"), ("31638", "2021_2026"), ("31477", "2021_2026"), ("30441", "2011_2016")):
    for nombre in (f"{n}-LEY.pdf", f"{n}.pdf", f"{n}-RESOLUCION LEGISLATIVA.pdf", f"{n}-LEY-RL.pdf"):
        for base in ("https://leyes.congreso.gob.pe/Documentos", "https://www.leyes.congreso.gob.pe/Documentos"):
            u = f"{base}/{per}/ADLP/Normas_Legales/{nombre}"
            try:
                r = requests.get(u, headers=A, timeout=40)
                if r.status_code == 200 or nombre.endswith("-LEY.pdf"):
                    print(r.status_code, len(r.content), r.content[:5], u)
            except Exception as e:
                print("ERR", u, str(e)[:80])
for u in ("https://www2.congreso.gob.pe/Sicr/TraDocEstProc/CLProLey2016.nsf", "https://leyes.congreso.gob.pe/LeyNume_1p.aspx?xEstado=2&xTipoNorma=0&xTipoBusqueda=4&xFechaI=&xFechaF=&xTexto=&ordenPor=0&xNormaI=30532&xNormaF=30532"):
    try:
        r = requests.get(u, headers=A, timeout=40); print(r.status_code, len(r.text), u[:90]); 
        import re; print(re.findall(r'href="([^"]+\.pdf)"', r.text, re.I)[:5])
    except Exception as e:
        print("ERR", u[:60], str(e)[:80])
