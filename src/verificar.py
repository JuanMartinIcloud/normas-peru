"""Verificacion completa: que cada norma tenga un enlace reconocible, que su PDF se descargue y
cuantas normas y proyectos tienen su texto completo indexado, por año. Escribe un reporte."""
import base64
import os
import random
import sys
from collections import defaultdict

import psycopg2
import requests

sys.path.insert(0, os.path.dirname(__file__))
from textos import AGENTE, EPDOC, codigo_norma  # noqa: E402

lineas = []
def p(x=""):
    print(x)
    lineas.append(x)

principal = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=60)
cm = principal.cursor()
cm.execute("SELECT hash_unico, fecha, url_detalle FROM normas")
normas = cm.fetchall()
cm.execute("SELECT periodo || '|' || camara || '|' || numero, extract(year from fecha_presentacion)::int FROM proyectos_ley WHERE num_pley IS NOT NULL")
proyectos = cm.fetchall()
principal.close()

# 1) Enlaces reconocibles
sin_codigo = [(h, f, u) for h, f, u in normas if not codigo_norma(u)]
p(f"# Verificacion de normas y proyectos")
p(f"Normas en el sistema: {len(normas):,}. Proyectos: {len(proyectos):,}.")
p(f"## 1. Enlaces de El Peruano reconocibles")
p(f"Normas cuyo enlace no permite obtener el PDF: {len(sin_codigo):,}")
for h, f, u in sin_codigo[:10]:
    p(f"- {f} {u}")

def formato(u):
    u = u or ""
    if "/dispositivo/" in u: return "dispositivo (2023+)"
    if "Referencias=" in u: return "epdoc Referencias"
    if "NormasElperuano" in u: return "NormasElperuano .html"
    if "/normaslegales/" in u: return "normaslegales/<titulo>"
    return "otro"

def descarga(cod, f):
    ref = base64.b64encode(f"{cod}{f.strftime('%Y%m%d')}".encode()).decode()
    r = requests.get(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE}, timeout=90)
    return r.content[:4] == b"%PDF", r.status_code

p("## 1b. Prueba de descarga por formato de enlace (3 por formato)")
por_formato = defaultdict(list)
for fila in normas:
    por_formato[formato(fila[2])].append(fila)
for fmt, filas in sorted(por_formato.items()):
    ok = 0
    muestra = random.sample(filas, min(3, len(filas)))
    for h, f, u in muestra:
        try:
            bien, st = descarga(codigo_norma(u), f)
            ok += bien
            if not bien:
                p(f"- {fmt}: sin PDF ({st}) {u}")
        except Exception as e:  # noqa: BLE001
            p(f"- {fmt}: error {str(e)[:100]} {u}")
    p(f"- {fmt} ({len(filas):,} normas): {ok} de {len(muestra)} PDF descargados")

# 2) Prueba real de descarga: 3 normas al azar por año
p("## 2. Prueba de descarga del PDF (3 normas al azar por año)")
por_anio = defaultdict(list)
for fila in normas:
    por_anio[fila[1].year].append(fila)
fallas = 0
for anio in sorted(por_anio):
    ok = 0
    muestra = random.sample(por_anio[anio], min(3, len(por_anio[anio])))
    for h, f, u in muestra:
        cod = codigo_norma(u)
        try:
            ref = base64.b64encode(f"{cod}{f.strftime('%Y%m%d')}".encode()).decode()
            r = requests.get(EPDOC, params={"Referencias": ref}, headers={"User-Agent": AGENTE}, timeout=90)
            if r.content[:4] == b"%PDF":
                ok += 1
            else:
                p(f"- {anio}: no devolvio PDF ({r.status_code}) {u}")
        except Exception as e:  # noqa: BLE001
            p(f"- {anio}: error {str(e)[:120]} {u}")
    fallas += len(muestra) - ok
    p(f"- {anio}: {ok} de {len(muestra)} PDF descargados")

# 3) Cobertura del texto completo
estado = {}
dup = 0
for i in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12):
    url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
    if not url:
        continue
    c = psycopg2.connect(url, connect_timeout=60); cur = c.cursor()
    cur.execute("SELECT tipo, clave, estado FROM documentos")
    for tipo, clave, est in cur.fetchall():
        k = (tipo.strip(), clave)
        if k in estado:
            dup += 1
            if est == "ok":
                estado[k] = est
        else:
            estado[k] = est
    c.close()

p("## 3. Normas: texto completo indexado por año")
p("| Año | Normas | Con texto | PDF escaneado (sin texto) | Sin PDF | Pendientes | % listo |")
p("| --- | --- | --- | --- | --- | --- | --- |")
tot = defaultdict(int)
for anio in sorted(por_anio):
    c = defaultdict(int)
    for h, f, u in por_anio[anio]:
        c[estado.get(("N", h), "pendiente")] += 1
    n = len(por_anio[anio]); listo = n - c["pendiente"]
    for k, v in c.items():
        tot[k] += v
    p(f"| {anio} | {n:,} | {c['ok']:,} | {c['sin_texto']:,} | {c['sin_pdf']:,} | {c['pendiente']:,} | {100*listo/n:.0f} % |")
n = len(normas)
p(f"| Total | {n:,} | {tot['ok']:,} | {tot['sin_texto']:,} | {tot['sin_pdf']:,} | {tot['pendiente']:,} | {100*(n-tot['pendiente'])/n:.0f} % |")

p("## 4. Proyectos de ley: texto completo indexado")
c = defaultdict(int)
for clave, anio in proyectos:
    c[estado.get(("P", clave), "pendiente")] += 1
n = len(proyectos)
p(f"Proyectos: {n:,} · con texto {c['ok']:,} · escaneados {c['sin_texto']:,} · sin PDF {c['sin_pdf']:,} · pendientes {c['pendiente']:,} · {100*(n-c['pendiente'])/n:.0f} % listo")
p(f"Documentos repetidos entre bases: {dup:,}")

os.makedirs("sondeo_buscador", exist_ok=True)
open("sondeo_buscador/verificacion.md", "w").write("\n".join(lineas) + "\n")
if sin_codigo or fallas:
    print(f"::warning title=Verificacion::{len(sin_codigo)} enlaces no reconocidos, {fallas} descargas de prueba fallidas")
