"""Prueba de las proposiciones convertidas en ley (00098-2026-2031-CD / 00013-2026-2031-S / Ley 32743).

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
EJEMPLO = "Cambios laborales (ejemplo)"


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
    ctx = nav.new_context(viewport={"width": 1366, "height": 900}, locale="es-PE")
    page = ctx.new_page(); page.set_default_timeout(120000); actual[0] = page

    @paso("ingreso")
    def _():
        ir(page, "/ingresar")
        page.locator("input[name=usuario]").fill(usuario)
        page.locator("input[name=clave]").fill(clave)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url(re.compile("/monitoreo"), timeout=60000)

    def tarjeta(ruta, texto, nombre):
        ir(page, ruta)
        art = page.locator("article", has_text=texto).first
        ver(page, art, 20)
        foto(page, nombre, art)
        nota(f"{nombre}: " + art.inner_text().replace("\n", " | ")[:900])

    @paso("proposicion de Diputados 00098")
    def _():
        tarjeta("/proyectos?q=00098-2026-2031-CD", "00098-2026-2031-CD", "b1_diputados")

    @paso("proposicion del Senado 00013")
    def _():
        tarjeta("/proyectos?q=00013-2026-2031-S", "00013-2026-2031-S", "b2_senado")

    @paso("filtro convertidas en ley")
    def _():
        ir(page, "/proyectos?estado=__ley")
        nota("opcion: " + page.locator("select[name=estado] option[value=__ley]").inner_text())
        nota("resumen: " + page.locator("p.resumen").first.inner_text())
        foto(page, "b3_filtro_ley")

    @paso("reporte del Congreso 22 de octubre, seccion 4")
    def _():
        ir(page, "/monitoreo/congreso?fecha=2026-10-22")
        h = page.get_by_role("heading", name=re.compile("Sección 4"))
        ver(page, h, 20)
        foto(page, "b4_congreso_leyes")
        nota("seccion 4: " + page.locator("main").inner_text().split("Sección 4")[-1].replace("\n", " | ")[:1200])

    @paso("resumen ejecutivo: fila de la 00098")
    def _():
        ir(page, "/monitoreo?mes=2026-10")
        fila = page.locator("tr", has_text="00098-2026-2031-CD").first
        ver(page, fila, 60)
        foto(page, "b5_tabla")
        nota("fila: " + fila.inner_text().replace("\n", " | ")[:700])

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
