import re, requests
A = {"User-Agent": "Mozilla/5.0"}
u = "https://busquedas.elperuano.pe/normaslegales/declaran-infundado-recurso-extraordinario-interpuesto-contra-resolucion-no-0411-2017-jne-1582046-1/"
h = requests.get(u, headers=A, timeout=60).text
print(len(h))
print(re.findall(r'<script[^>]*>', h)[:20])
print(re.findall(r'(?:src|href)="([^"]+)"', h)[:60])
i = h.find("Cuadernillo")
print(h[i-1500:i+800])
