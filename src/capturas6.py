"""Capturas de los correos que envia el sistema: informe diario (general y por comite) y busqueda guardada.

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



FECHA = "2026-10-22"


def correo_busqueda(b, r, sitio):
    """Mismo formato que htmlEjecucion (web/lib/busquedas.js)."""
    import html as h
    e = lambda s: h.escape(str(s if s is not None else ""), quote=True)  # noqa: E731
    def lista(items, campo):
        if not items:
            return '<p style="color:#666">Sin resultados.</p>'
        return "<ul>" + "".join(
            f'<li><a href="{e(x.get("url"))}">{e(x.get("nombre"))}</a> ({e(x.get("fecha"))}) — {e(x.get(campo))}</li>' if x.get("url")
            else f'<li>{e(x.get("nombre"))} ({e(x.get("fecha"))}) — {e(x.get(campo))}</li>' for x in items[:40]) + "</ul>"
    res = r.get("resumen") or {}
    resumen = (f'<h2 style="font-size:16px">Resumen</h2><p>{e(res.get("panorama"))}</p><ul>' +
               "".join(f"<li>{e(p)}</li>" for p in res.get("puntos", [])) + "</ul>") if res and not res.get("error") else ""
    return f"""<div style="font-family:Arial,sans-serif;max-width:760px;color:#222;padding:16px">
<h1 style="font-size:20px;color:#8f1d2c">{e(b["nombre"])}</h1>
<p style="color:#555">Búsqueda guardada: «{e(b["pregunta"])}» · del {e(r["desde"])} al {e(r["hasta"])} ·
{r["total_normas"]} normas legales y {r["total_proyectos"]} proyectos de ley.</p>
{resumen}
<h2 style="font-size:16px">Normas legales ({r["total_normas"]})</h2>{lista(r["normas"], "sumilla")}
<h2 style="font-size:16px">Proyectos de ley ({r["total_proyectos"]})</h2>{lista(r["proyectos"], "titulo")}
<p><a href="{e(sitio)}">Ver todos los resultados en el buscador</a></p></div>"""


with sync_playwright() as pw:
    nav = pw.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1100, "height": 900}, locale="es-PE")
    page = ctx.new_page(); page.set_default_timeout(120000); actual[0] = page
    page.on("dialog", lambda d: d.accept())

    @paso("ingreso")
    def _():
        ir(page, "/ingresar")
        page.locator("input[name=usuario]").fill(usuario)
        page.locator("input[name=clave]").fill(clave)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url(re.compile("/monitoreo"), timeout=60000)

    @paso("informe: pagina y correo general")
    def _():
        ir(page, f"/monitoreo/informe?fecha={FECHA}")
        sin_temporal(page)
        foto(page, "c1_informe_pagina")
        caja = page.locator("h2#vista + p + div.grafico, h2#vista + div.grafico").first
        foto(page, "c2_correo_general", loc=caja)

    @paso("informe: correo de un comite")
    def _():
        ir(page, f"/monitoreo/informe?fecha={FECHA}")
        enlace = page.locator("table.tabla-mon a").first
        nota("comite: " + enlace.inner_text())
        enlace.click(); page.wait_for_load_state("networkidle")
        caja = page.locator("div.grafico").last
        foto(page, "c3_correo_comite", loc=caja)

    @paso("correo de busqueda guardada")
    def _():
        ir(page, "/monitoreo/busquedas")
        f = page.locator("form").filter(has_text="Crear búsqueda guardada")
        f.locator("input[name=pregunta]").fill("cambios en las obligaciones laborales de las empresas")
        f.locator("input[name=nombre]").fill(EJEMPLO)
        f.locator("select[name=frecuencia]").select_option("mensual")
        f.get_by_role("button", name="Crear búsqueda guardada").click()
        page.locator("article", has_text=EJEMPLO).first.wait_for(timeout=120000)
        page.locator("article", has_text=EJEMPLO).first.get_by_role("button", name="Ejecutar ahora").click()
        page.get_by_text(re.compile(r"Listo: ")).first.wait_for(timeout=300000)
        d = psycopg2.connect(os.environ["DATABASE_URL"]); c = d.cursor()
        c.execute("""SELECT b.nombre, coalesce(b.pregunta, b.q), e.desde::text, e.hasta::text, e.total_normas, e.total_proyectos,
                            e.normas, e.proyectos, e.resumen
                     FROM busqueda_ejecuciones e JOIN busquedas_guardadas b ON b.id = e.busqueda_id
                     WHERE b.nombre = %s ORDER BY e.creado_en DESC LIMIT 1""", (EJEMPLO,))
        n, q, de, ha, tn, tp, ns, ps, rs = c.fetchone(); d.close()
        html = correo_busqueda({"nombre": n, "pregunta": q}, {"desde": de, "hasta": ha, "total_normas": tn, "total_proyectos": tp,
                                "normas": ns or [], "proyectos": ps or [], "resumen": rs}, BASE + "/buscar")
        p2 = ctx.new_page(); p2.set_content(html); p2.wait_for_timeout(500)
        p2.screenshot(path=f"{SALIDA}/c4_correo_busqueda.png", full_page=True); p2.close()

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
