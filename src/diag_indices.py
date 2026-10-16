import requests
A = {"User-Agent": "Mozilla/5.0"}
B = "https://leyes.congreso.gob.pe/Documentos"
pruebas = []
for n in ("30440", "30474", "30479", "31638", "31477", "31365"):
    pruebas += [f"{B}/Leyes/{n}.pdf", f"{B}/leyes/{n}.pdf", f"{B}/2021_2026/ADLP/Normas_Legales/{n}.pdf",
                f"{B}/2021_2026/ADLP/Normas_Legales/{n}-LEY.PDF", f"{B}/2021_2026/ADLP/Normas_Legales/{n}%20LEY.pdf",
                f"{B}/2011_2016/ADLP/Normas_Legales/{n}.pdf"]
for n in ("30441", "30444", "30480", "30531", "30675"):
    pruebas += [f"{B}/ResLegislativas/{n}.pdf", f"{B}/2016_2021/ADLP/Normas_Legales/{n}-RL.pdf", f"{B}/2016_2021/ADLP/Normas_Legales/{n}-RESLEG.pdf",
                f"{B}/2016_2021/ADLP/Normas_Legales/{n}-LEY.pdf"]
for u in pruebas:
    try:
        r = requests.get(u, headers=A, timeout=40)
        print(r.status_code, len(r.content), r.content[:5], u)
    except Exception as e:
        print("ERR", u, str(e)[:60])
