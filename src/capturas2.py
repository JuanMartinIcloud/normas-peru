"""Segunda tanda de capturas para el manual detallado: cada opcion y lo que hay dentro de cada una.

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

    # ------------------------------------------------------------------ Ingreso
    @paso("ingreso con error")
    def _():
        ir(page, "/ingresar")
        page.locator("input[name=usuario]").fill("maria.lopez")
        page.locator("input[name=clave]").fill("clave-equivocada")
        page.get_by_role("button", name="Ingresar").click()
        page.locator("p.ia-aviso").wait_for(timeout=30000)
        foto(page, "x01_ingreso_error")

    @paso("ingreso")
    def _():
        ir(page, "/ingresar")
        page.locator("input[name=usuario]").fill(usuario)
        page.locator("input[name=clave]").fill(clave)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url(re.compile("/monitoreo"), timeout=60000)

    # ------------------------------------------------------------------ Portada
    @paso("portada resumen del dia")
    def _():
        ir(page, "/")
        r = page.locator("section.ia").first
        ver(page, page.get_by_role("link", name="Resúmenes anteriores"), 500)
        foto(page, "x10_resumen_dia_final")
        page.locator("section.ia summary").first.click()
        page.evaluate("() => window.scrollTo(0, 0)")
        foto(page, "x11_resumen_dia_plegado")

    @paso("portada atajos")
    def _():
        ir(page, "/")
        page.get_by_role("link", name="Leyes y normas con rango de ley").click(); page.wait_for_load_state("networkidle")
        foto(page, "x12_leyes")
        ir(page, "/")
        page.get_by_role("link", name=re.compile(r"^2020 ·")).click(); page.wait_for_load_state("networkidle")
        foto(page, "x13_anio_2020")

    @paso("portada filtros rubro y fechas")
    def _():
        ir(page, "/")
        page.locator("select[name=rubro]").select_option(label=re.compile("^Tributario y Aduanero"))
        page.locator("input[name=desde]").fill("2026-09-01")
        page.locator("input[name=hasta]").fill("2026-09-30")
        foto(page, "x14_filtros_llenos", loc=page.locator("form.filtros"))
        page.locator("form.filtros button[type=submit]").click(); page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 330)
        foto(page, "x15_filtros_resultado")
        ver(page, page.locator("div.paginas"), 400)
        foto(page, "x16_paginas")

    @paso("portada resumir")
    def _():
        ir(page, "/?rubro=Tributario+y+Aduanero&desde=2026-09-01&hasta=2026-09-30")
        b = page.get_by_role("button", name="✦ Resumir con IA"); ver(page, b, 300); b.click()
        page.get_by_text("Resumen con IA de esta búsqueda").wait_for(timeout=200000)
        sec = page.locator("section.ia").last
        foto(page, "x17_portada_resumen_ia", loc=sec)

    # ------------------------------------------------------------------ Buscar en todo
    url = {}

    @paso("buscar con IA")
    def _():
        ir(page, "/buscar")
        page.evaluate("() => { try { localStorage.setItem('normas-peru-buscar-con-ia', '1') } catch (e) {} }")
        ir(page, "/buscar")
        page.locator("input[name=q]").fill("normas que afecten las inversiones privadas en minería")
        page.locator("form.filtros button[type=submit]").click()
        page.wait_for_url(re.compile("pregunta="), timeout=120000); page.wait_for_load_state("networkidle")
        url["ia"] = page.url

    @paso("quitar un termino")
    def _():
        page.goto(url["ia"], wait_until="networkidle")
        ver(page, page.locator("p.terminos").first, 250)
        foto(page, "x20_antes_quitar_termino", loc=page.locator("p.terminos").first)
        page.locator("p.terminos a.etq").last.click(); page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 40)
        foto(page, "x21_despues_quitar_termino")

    @paso("cinco filtros")
    def _():
        page.goto(url["ia"], wait_until="networkidle")
        for palabra in ["tributario", "regalía", "contrato", "estabilidad", "garantía"]:
            page.locator("form.refinar input").fill(palabra)
            page.locator("form.refinar button").click()
            page.wait_for_function("(w) => decodeURIComponent(location.search).includes(w)", arg=palabra, timeout=90000)
            page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 40)
        foto(page, "x22_cinco_filtros")

    @paso("ver todas las normas")
    def _():
        page.goto(url["ia"], wait_until="networkidle")
        l = page.get_by_role("link", name=re.compile("^Ver las .* normas con más filtros"))
        ver(page, l, 300); foto(page, "x23_enlace_ver_todas")
        l.click(); page.wait_for_load_state("networkidle")
        foto(page, "x24_ver_todas_resultado")

    @paso("resumen ia completo")
    def _():
        page.goto(url["ia"], wait_until="networkidle")
        b = page.get_by_role("button", name="✦ Resumir con IA"); ver(page, b, 300); b.click()
        page.get_by_text("Resumen con IA de esta búsqueda").wait_for(timeout=200000)
        foto(page, "x25_resumen_ia_completo", loc=page.locator("section.ia").last)

    @paso("guardar busqueda y confirmacion")
    def _():
        page.goto(url["ia"], wait_until="networkidle")
        page.get_by_role("button", name="★ Guardar esta búsqueda").click()
        page.locator("input[name=nombre]").fill(EJEMPLO)
        page.locator("select[name=frecuencia]").select_option("semanal")
        page.locator("input[name=destinatarios]").fill("legal@empresa.com")
        f = page.locator("form.filtros").last; ver(page, f, 60)
        foto(page, "x26_guardar_lleno", loc=f)
        page.get_by_role("button", name="Guardar búsqueda").click()
        page.get_by_text("Búsqueda guardada.").wait_for(timeout=60000)
        foto(page, "x27_guardar_confirmacion", loc=page.locator("p.ia-aviso", has_text="Búsqueda guardada"))

    @paso("seleccionar proyectos y proyecto unificado")
    def _():
        page.evaluate("() => { try { localStorage.removeItem('normas-peru-seleccion') } catch (e) {} }")
        ir(page, "/proyectos?q=convivencia+sin+violencia")
        m = page.locator("article.norma label.marcar input")
        m.nth(0).check(); m.nth(1).check()
        foto(page, "x30_dos_proyectos_barra")
        page.get_by_role("link", name="Proponer proyecto unificado").click(); page.wait_for_load_state("networkidle")
        foto(page, "x31_proyecto_unificado_pantalla")
        page.get_by_role("button", name="✦ Redactar proyecto unificado").click()
        page.get_by_role("heading", name="Documentos de origen").or_(page.locator("p.ia-aviso")).first.wait_for(timeout=330000)
        foto(page, "x32_proyecto_unificado_resultado", loc=page.locator("section.documento"))
        b = page.get_by_role("button", name="Descargar en Word")
        b.scroll_into_view_if_needed()
        page.evaluate("() => window.scrollBy(0, 300)")
        foto(page, "x33_botones_word")
        page.evaluate("() => { try { localStorage.clear() } catch (e) {} }")

    @paso("busqueda sin IA y ampliar")
    def _():
        ir(page, "/buscar")
        page.locator("label.check input").uncheck()
        foto(page, "x34_sin_ia_casilla", loc=page.locator("form.filtros"))
        page.evaluate("() => { try { localStorage.setItem('normas-peru-buscar-con-ia', '1') } catch (e) {} }")

    # ------------------------------------------------------------------ Proyectos
    @paso("proyectos filtros")
    def _():
        ir(page, "/proyectos")
        page.locator("select[name=periodo]").select_option(label=re.compile("^2026"))
        page.locator("select[name=estado]").select_option(label=re.compile("^EN COMISI"))
        foto(page, "x40_proyectos_filtros", loc=page.locator("form.filtros"))
        page.locator("form.filtros button[type=submit]").click(); page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 80)
        foto(page, "x41_proyectos_resultado")
        foto(page, "x42_proyecto_tarjeta", loc=page.locator("article.norma").first)

    @paso("resumenes otro dia")
    def _():
        ir(page, "/resumenes")
        page.locator("div.anios a.atajo").nth(2).click(); page.wait_for_load_state("networkidle")
        foto(page, "x45_resumen_otro_dia")

    # ------------------------------------------------------------------ Monitoreo
    @paso("ejecutivo completo")
    def _():
        ir(page, "/monitoreo")
        b = page.locator("button", has_text="resumen ejecutivo"); ver(page, b, 300); b.click()
        page.get_by_text("Puntos clave").wait_for(timeout=240000)
        foto(page, "x50_ejecutivo_completo", loc=page.locator("div.resumen-ia"))
        t = page.get_by_role("heading", name="Documentos de impacto alto"); ver(page, t, 30)
        foto(page, "x51_impacto_alto")

    @paso("ejecutivo por dia")
    def _():
        ir(page, "/monitoreo?fecha=2026-10-14")
        foto(page, "x52_ejecutivo_dia")

    @paso("normas filtro desfavorable")
    def _():
        ir(page, "/monitoreo/normas")
        page.locator("select[name=calificacion]").select_option("Desfavorable")
        page.locator("form.filtros button[type=submit]").click(); page.wait_for_load_state("networkidle")
        ver(page, page.locator("p.resumen"), 380)
        foto(page, "x53_normas_desfavorables")

    @paso("quitar y devolver")
    def _():
        ir(page, "/monitoreo/normas")
        t = page.locator("article.tarjeta-mon").first
        ver(page, t.get_by_role("button", name=re.compile("Quitar del reporte")), 300)
        foto(page, "x54_antes_quitar", loc=t)
        t.get_by_role("button", name=re.compile("Quitar del reporte")).click()
        t.get_by_role("button", name=re.compile("Devolver al reporte")).wait_for(timeout=30000)
        ir(page, "/monitoreo/normas?quitados=1")
        t2 = page.locator("article.tarjeta-mon.quitado").first
        ver(page, t2, 30)
        foto(page, "x55_quitado", loc=t2)
        t2.get_by_role("button", name=re.compile("Devolver al reporte")).click()
        page.wait_for_timeout(2500)

    @paso("congreso dia con items")
    def _():
        ir(page, "/monitoreo/congreso?fecha=2026-10-13")
        foto(page, "x56_congreso_dia")
        t = page.locator("article.tarjeta-mon").first
        ver(page, t, 30)
        foto(page, "x57_congreso_tarjeta", loc=t)

    @paso("impacto comite abierto")
    def _():
        ir(page, "/monitoreo/impacto")
        s = page.locator("details.otros summary", has_text="Minería").first
        ver(page, s, 60); s.click()
        foto(page, "x58_comite_abierto")
        t = page.get_by_role("heading", name="Detalle por documento"); ver(page, t, 30)
        foto(page, "x59_detalle_documento")

    @paso("informe aprobar y volver")
    def _():
        ir(page, "/monitoreo/informe?fecha=2026-10-14")
        estado_inicial = page.locator("div.grafico").first.inner_text()
        if "Borrador" in estado_inicial:
            page.get_by_role("button", name="Aprobar informe").click()
            page.get_by_role("button", name="Volver a borrador").wait_for(timeout=30000)
            foto(page, "x60_informe_aprobado", loc=page.locator("div.grafico").first)
            page.get_by_role("button", name="Volver a borrador").click()
            page.get_by_role("button", name="Aprobar informe").wait_for(timeout=30000)
        h = page.get_by_role("heading", name=re.compile("Vista previa del correo"))
        ver(page, h, 30); foto(page, "x61_vista_previa")
        s = page.locator("summary", has_text="Destinatarios del correo"); ver(page, s, 60); s.click()
        foto(page, "x62_destinatarios_abierto")

    @paso("busquedas editar pausar ejecutar")
    def _():
        ir(page, "/monitoreo/busquedas")
        art = page.locator("article", has_text=EJEMPLO).first
        art.get_by_role("button", name="Editar").click()
        ver(page, art, 30); foto(page, "x63_busqueda_editar", loc=art)
        art.get_by_role("button", name="Editar").click()
        art.get_by_role("button", name="Pausar").click(); page.wait_for_timeout(2500); page.wait_for_load_state("networkidle")
        art = page.locator("article", has_text=EJEMPLO).first
        ver(page, art, 30); foto(page, "x64_busqueda_pausada", loc=art)
        art.get_by_role("button", name="Activar").click(); page.wait_for_timeout(2500); page.wait_for_load_state("networkidle")
        art = page.locator("article", has_text=EJEMPLO).first
        art.get_by_role("button", name="Ejecutar ahora").click()
        art.locator("span.ia-pendiente").wait_for(timeout=240000)
        foto(page, "x65_busqueda_ejecutada", loc=art)
        page.wait_for_timeout(2500)
        ir(page, "/monitoreo/busquedas")
        page.locator("article", has_text=EJEMPLO).first.get_by_role("link", name="Ver resultados").click()
        page.wait_for_load_state("networkidle")
        foto(page, "x66_busqueda_detalle", completa=True)

    @paso("usuarios crear lleno")
    def _():
        ir(page, "/monitoreo/usuarios")
        sin_temporal(page)
        page.locator("form.filtros input[name=nombre]").fill("María López")
        page.locator("form.filtros input[name=usuario]").fill("maria.lopez")
        page.locator("form.filtros input[name=clave]").fill("unaclave123")
        page.locator("form.filtros select[name=rol]").select_option("editor")
        foto(page, "x67_usuario_formulario")

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
