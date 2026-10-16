import re, requests
A = {"User-Agent": "Mozilla/5.0"}
B = "https://busquedas.elperuano.pe"
def datos(h):
    out = []
    for pat in (r'urlPDF\\?"[,:]\\?"?([^"\\]+)', r'\\"(https?://[^"\\]+\.pdf)\\"', r'fechaPublicacion\\?"[,:]\\?"?([^"\\,]+)', r'hasHTML\\?"[,:]([a-z]+)', r'paginas\\?"[,:]([0-9]+)'):
        out.append((pat[:12], re.findall(pat, h)[:4]))
    return out
for u in ("/dispositivo/NL/1582046-1", "/normaslegales/dejan-sin-efecto-designaciones-y-designan-fed"):
    h = requests.get(B + u, headers=A, timeout=60).text
    print(u, len(h), datos(h))
    i = h.find("urlPDF"); print(h[i-300:i+500] if i >= 0 else "sin urlPDF")
for f in ("2017-11-01", "20171101", "01/11/2017"):
    r = requests.get(f"{B}/cuadernillo/NL/{f}", headers=A, timeout=60)
    print("\nCUADERNILLO", f, r.status_code, len(r.text), datos(r.text))
    i = r.text.find(".pdf"); print(r.text[max(0, i-400):i+200] if i >= 0 else "")
