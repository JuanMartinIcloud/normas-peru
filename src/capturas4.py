"""Cuarta tanda (portada con rubros corregidos) de capturas para el manual detallado: cada opcion y lo que hay dentro de cada una.

Usa un usuario temporal (se borra al final). Todo lo que cambia datos (quitar un item, aprobar el informe,
pausar una busqueda) se deja como estaba al terminar.
"""
import hashlib
import os
import re
import secrets

import psycopg2
from playwright.sync_api import sync_playwright

BASE = "https://normas-peru.vercel.app"
SALIDA = "capturas"
os.makedirs(SALIDA, exist_ok=True)
notas = []
actual = [None]

db = psycopg2.connect(os.environ["DATABASE_URL"]); db.autocommit = True; cur = db.cursor()
cur.execute("DELETE FROM usuarios WHERE usuario LIKE 'manual-%%'")
clave = secrets.token_hex(12); sal = secrets.token_bytes(16)
h = hashlib.scrypt(clave.encode(), salt=sal, n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
usuario = f"manual-{secrets.token_hex(3)}"
cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (%s, 'Administrador', %s, 'admin') RETURNING id",
            (usuario, f"scrypt${sal.hex()}${h.hex()}"))
uid = cur.fetchone()[0]
db.close()
EJEMPLO = "Minería e inversiones (ejemplo del manual)"


def nota(t):
    print(t, flush=True); notas.append(t)


def paso(nombre):
    def deco(f):
        try:
            f(); nota(f"OK   {nombre}")
        except Exception as e:  # noqa: BLE001
            nota(f"FALLA {nombre}: {str(e)[:300]}")
            try:
                actual[0].screenshot(path=f"{SALIDA}/ERROR_{re.sub(r'\W+', '_', nombre)}.png", full_page=True)
            except Exception:  # noqa: BLE001
                pass
        return f
    return deco


def foto(page, nombre, loc=None, completa=False):
    page.wait_for_timeout(700)
    ruta = f"{SALIDA}/{nombre}.png"
    if loc is not None:
        loc.screenshot(path=ruta)
    else:
        page.screenshot(path=ruta, full_page=completa)


def ir(page, ruta):
    page.goto(BASE + ruta, wait_until="networkidle", timeout=120000)


def ver(page, loc, arriba=90):
    loc.scroll_into_view_if_needed(timeout=20000)
    page.evaluate("(y) => window.scrollBy(0, -y)", arriba)
    page.wait_for_timeout(400)


def sin_temporal(page):
    page.evaluate("() => document.querySelectorAll('tr').forEach(tr => { if (tr.textContent.includes('manual-')) tr.remove(); })")


with sync_playwright() as pw:
    nav = pw.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1366, "height": 880}, locale="es-PE")
    page = ctx.new_page(); page.set_default_timeout(60000); actual[0] = page
    page.on("dialog", lambda d: d.accept())   # confirmaciones (eliminar) y avisos

    @paso("ingreso")
    def _():
        ir(page, "/ingresar")
        page.locator("input[name=usuario]").fill(usuario)
        page.locator("input[name=clave]").fill(clave)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url(re.compile("/monitoreo"), timeout=60000)

    @paso("portada filtros rubro y fechas")
    def _():
        ir(page, "/")
        page.locator("select[name=rubro]").select_option(value="Tributario y Aduanero")
        page.locator("input[name=desde]").fill("2026-09-01")
        page.locator("input[name=hasta]").fill("2026-09-30")
        foto(page, "x14_filtros_llenos", loc=page.locator("form.filtros"))
        page.locator("form.filtros button[type=submit]").click(); page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 330)
        foto(page, "x15_filtros_resultado")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        foto(page, "x16_paginas")

    @paso("portada resumir")
    def _():
        ir(page, "/?rubro=Tributario+y+Aduanero&desde=2026-09-01&hasta=2026-09-30")
        b = page.get_by_role("button", name="✦ Resumir con IA"); ver(page, b, 300); b.click()
        page.get_by_text("Resumen con IA de esta búsqueda").wait_for(timeout=200000)
        sec = page.locator("section.ia").last
        foto(page, "x17_portada_resumen_ia", loc=sec)

    nav.close()

# Limpieza con conexion nueva
try:
    d2 = psycopg2.connect(os.environ["DATABASE_URL"]); d2.autocommit = True; c2 = d2.cursor()
    c2.execute("DELETE FROM busquedas_guardadas WHERE nombre = %s", (EJEMPLO,))
    c2.execute("DELETE FROM usuarios WHERE usuario LIKE 'manual-%%'")
    d2.close()
except Exception as e:  # noqa: BLE001
    nota(f"limpieza: {e}")
with open(f"{SALIDA}/notas.txt", "w") as f:
    f.write("\n".join(notas))
