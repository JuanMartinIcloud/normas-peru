import re, requests
A = {"User-Agent": "Mozilla/5.0"}
B = "https://busquedas.elperuano.pe"
h = requests.get(B + "/dispositivo/NL/2068624-1", headers=A, timeout=60).text
print(len(h))
i = h.find("tipoEdicion"); print(h[max(0, i-1500): i+1500])
for q in ("NL20220518", "NL20220518?", "NL20220518*", "31477"):
    r = requests.get(B + "/", params={"query": q}, headers=A, timeout=60)
    print("\nBUSCA", q, r.status_code, list(dict.fromkeys(re.findall(r'(/api/archivo/file/[^"\\]+\.pdf)', r.text)))[:10])
for u in ("https://leyes.congreso.gob.pe/Documentos/2021_2026/ADLP/Normas_Legales/31477-LEY.pdf",
          "https://leyes.congreso.gob.pe/Documentos/2016_2021/ADLP/Normas_Legales/31098-RESOLUCION%20LEGISLATIVA.pdf"):
    try:
        r = requests.get(u, headers=A, timeout=60); print(u[-40:], r.status_code, len(r.content), r.content[:8])
    except Exception as e:
        print(u, e)
