"""Capturas de pantalla de la web publicada, paso a paso, para el manual de usuario.

Crea un usuario temporal (se borra al final), recorre cada pantalla y cada accion, y guarda las imagenes
en la carpeta capturas/. Cada paso es independiente: si uno falla, se anota y se sigue con el siguiente.
"""
import hashlib
import os
import secrets
import time

import psycopg2
from playwright.sync_api import sync_playwright

BASE = "https://normas-peru.vercel.app"
SALIDA = "capturas"
os.makedirs(SALIDA, exist_ok=True)
notas = []

db = psycopg2.connect(os.environ["DATABASE_URL"])
db.autocommit = True
cur = db.cursor()
clave = secrets.token_hex(12)
sal = secrets.token_bytes(16)
h = hashlib.scrypt(clave.encode(), salt=sal, n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
usuario = f"manual-{secrets.token_hex(3)}"
cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES (%s, 'Administrador', %s, 'admin') RETURNING id",
            (usuario, f"scrypt${sal.hex()}${h.hex()}"))
uid = cur.fetchone()[0]
NOMBRE_BUSQUEDA = "Tributación minera (ejemplo del manual)"


def nota(t):
    print(t, flush=True)
    notas.append(t)


def paso(nombre):
    def deco(f):
        def envuelta(*a, **k):
            try:
                f(*a, **k)
                nota(f"OK   {nombre}")
            except Exception as e:  # noqa: BLE001
                nota(f"FALLA {nombre}: {str(e)[:300]}")
        return envuelta
    return deco


def foto(page, nombre, loc=None, completa=False):
    page.wait_for_timeout(600)
    ruta = f"{SALIDA}/{nombre}.png"
    if loc is not None:
        loc.screenshot(path=ruta)
    else:
        page.screenshot(path=ruta, full_page=completa)


def ir(page, ruta):
    page.goto(BASE + ruta, wait_until="networkidle", timeout=120000)


def a_la_vista(page, loc, arriba=90):
    loc.scroll_into_view_if_needed(timeout=20000)
    page.evaluate("(y) => window.scrollBy(0, -y)", arriba)
    page.wait_for_timeout(400)


with sync_playwright() as pw:
    nav = pw.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1366, "height": 880}, device_scale_factor=1, locale="es-PE")
    page = ctx.new_page()
    page.set_default_timeout(60000)

    @paso("ingresar")
    def ingresar():
        ir(page, "/ingresar")
        foto(page, "01_ingresar")
        page.locator("input[name=usuario]").fill("maria.lopez")
        page.locator("input[name=clave]").fill("contraseña")
        foto(page, "02_ingresar_lleno")
        page.locator("input[name=usuario]").fill(usuario)
        page.locator("input[name=clave]").fill(clave)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url("**/monitoreo**", timeout=60000)
    ingresar()

    # ------------------------------------------------------------------ Normas legales (portada)
    @paso("portada")
    def portada():
        ir(page, "/")
        foto(page, "10_portada_arriba")
        a_la_vista(page, page.get_by_role("heading", name="Por año"))
        foto(page, "11_portada_por_anio")
        a_la_vista(page, page.locator("form.filtros"))
        foto(page, "12_portada_filtros")
        a_la_vista(page, page.locator("article.norma").first)
        foto(page, "13_portada_resultados")
        foto(page, "14_portada_una_norma", loc=page.locator("article.norma").first)
    portada()

    @paso("portada hoy")
    def portada_hoy():
        ir(page, "/")
        page.get_by_role("link", name="Hoy", exact=True).click()
        page.wait_for_load_state("networkidle")
        foto(page, "15_portada_hoy")
    portada_hoy()

    @paso("portada buscar palabra")
    def portada_palabra():
        ir(page, "/")
        page.locator("input[name=q]").fill("teletrabajo")
        page.locator("label.check:has-text('Solo gobierno central') input").check()
        foto(page, "16_portada_buscar_escrito", loc=page.locator("form.filtros"))
        page.locator("form.filtros button[type=submit]").click()
        page.wait_for_load_state("networkidle")
        a_la_vista(page, page.locator("p.resumen"), 260)
        foto(page, "17_portada_buscar_resultado")
    portada_palabra()

    # ------------------------------------------------------------------ Buscar en todo (con IA)
    @paso("buscar con IA")
    def buscar_ia():
        ir(page, "/buscar")
        page.evaluate("() => { try { localStorage.setItem('normas-peru-buscar-con-ia', '1') } catch (e) {} }")
        ir(page, "/buscar")
        foto(page, "20_buscar_vacio")
        page.locator("input[name=q]").fill("normas que afecten las inversiones privadas en minería")
        foto(page, "21_buscar_escrito")
        page.locator("form.filtros button[type=submit]").click()
        page.wait_for_timeout(700)
        foto(page, "22_buscar_ia_pensando")
        page.wait_for_url("**pregunta=**", timeout=120000)
        page.wait_for_load_state("networkidle")
        foto(page, "23_buscar_resultado_arriba")
        a_la_vista(page, page.locator("p.terminos").first, 200)
        foto(page, "24_buscar_terminos_y_botones")
        a_la_vista(page, page.locator("h2.seccion", has_text="Normas legales"))
        foto(page, "25_buscar_normas")
        a_la_vista(page, page.locator("h2.seccion", has_text="Proyectos de ley"))
        foto(page, "26_buscar_proyectos")
    buscar_ia()
    url_busqueda = page.url

    @paso("filtros 1 y 2")
    def filtros():
        page.goto(url_busqueda, wait_until="networkidle")
        caja = page.locator("form.refinar input")
        a_la_vista(page, caja, 300)
        caja.fill("tributario")
        foto(page, "27_filtro1_escrito")
        page.locator("form.refinar button").click()
        page.wait_for_url("**y=**", timeout=90000)
        page.wait_for_load_state("networkidle")
        a_la_vista(page, page.locator("form.refinar"), 330)
        foto(page, "28_filtro1_resultado")
        page.locator("form.refinar input").fill("regalía")
        page.locator("form.refinar button").click()
        page.wait_for_function("() => decodeURIComponent(location.search).includes('regal')", timeout=90000)
        page.wait_for_load_state("networkidle")
        a_la_vista(page, page.locator("form.refinar"), 330)
        foto(page, "29_filtro2_resultado")
    filtros()
    url_filtrada = page.url

    @paso("resumir con IA")
    def resumir():
        page.goto(url_busqueda, wait_until="networkidle")
        b = page.get_by_role("button", name="✦ Resumir con IA")
        a_la_vista(page, b, 300)
        b.click()
        page.wait_for_timeout(1500)
        foto(page, "30_resumir_esperando")
        t = page.get_by_text("Resumen con IA de esta búsqueda")
        t.wait_for(timeout=200000)
        a_la_vista(page, t, 40)
        foto(page, "31_resumen_ia")
        foto(page, "32_resumen_ia_completo", completa=True)
    resumir()

    @paso("guardar busqueda (formulario)")
    def guardar():
        page.goto(url_busqueda, wait_until="networkidle")
        b = page.get_by_role("button", name="★ Guardar esta búsqueda")
        a_la_vista(page, b, 300)
        b.click()
        page.wait_for_timeout(800)
        foto(page, "33_guardar_formulario")
        page.get_by_role("button", name="Cancelar").click()
    guardar()

    @paso("seleccionar y unir")
    def unir():
        page.goto(url_busqueda, wait_until="networkidle")
        marcas = page.locator("article.norma label.marcar input")
        marcas.nth(0).check()
        marcas.nth(1).check()
        a_la_vista(page, marcas.nth(0), 200)
        foto(page, "34_seleccionar_dos")
        page.get_by_role("link", name="Unir en un texto").click()
        page.wait_for_load_state("networkidle")
        foto(page, "35_unir_pantalla")
        page.get_by_role("button", name="✦ Unir con IA").click()
        page.wait_for_timeout(3000)
        foto(page, "36_unir_esperando")
        page.get_by_role("heading", name="Documentos de origen").wait_for(timeout=330000)
        ir_arriba = page.locator("section.documento")
        a_la_vista(page, ir_arriba, 20)
        foto(page, "37_unir_resultado")
        a_la_vista(page, page.get_by_role("button", name="Descargar en Word"), 500)
        foto(page, "38_unir_botones")
    unir()

    @paso("proyecto unificado (pantalla)")
    def proyecto_unificado():
        ir(page, "/unir?accion=proyecto")
        foto(page, "39_proyecto_unificado")
        page.evaluate("() => { try { localStorage.clear() } catch (e) {} }")
    proyecto_unificado()

    # ------------------------------------------------------------------ Buscar sin IA, con un error de tipeo
    @paso("buscar sin IA")
    def sin_ia():
        ir(page, "/buscar")
        page.locator("label.check input").uncheck()
        page.locator("input[name=q]").fill("violencia piscologica")
        foto(page, "40_sin_ia_escrito")
        page.locator("form.filtros button[type=submit]").click()
        page.wait_for_url("**q=**", timeout=60000)
        page.wait_for_load_state("networkidle")
        foto(page, "41_sin_ia_corregido")
        amp = page.get_by_role("button", name="✦ Ampliar la búsqueda con IA")
        if amp.count():
            a_la_vista(page, amp, 300)
            foto(page, "42_ampliar_boton")
            amp.click()
            page.wait_for_url("**t=**", timeout=120000)
            page.wait_for_load_state("networkidle")
            foto(page, "43_ampliar_resultado")
        page.evaluate("() => { try { localStorage.setItem('normas-peru-buscar-con-ia', '1') } catch (e) {} }")
    sin_ia()

    # ------------------------------------------------------------------ Proyectos de ley
    @paso("proyectos")
    def proyectos():
        ir(page, "/proyectos")
        foto(page, "50_proyectos_arriba")
        page.locator("input[name=q]").fill("pensiones")
        page.locator("form.filtros button[type=submit]").click()
        page.wait_for_load_state("networkidle")
        a_la_vista(page, page.locator("p.resumen"), 200)
        foto(page, "51_proyectos_resultado")
        foto(page, "52_proyectos_uno", loc=page.locator("article.norma").first)
        page.locator("article.norma").first.get_by_role("link", name="Similares").click()
        page.wait_for_load_state("networkidle")
        foto(page, "53_proyectos_similares")
    proyectos()

    @paso("resumenes")
    def resumenes():
        ir(page, "/resumenes")
        foto(page, "55_resumenes_arriba")
        foto(page, "56_resumenes_completo", completa=True)
    resumenes()

    # ------------------------------------------------------------------ Monitoreo empresarial
    @paso("monitoreo resumen")
    def mon_resumen():
        ir(page, "/monitoreo")
        foto(page, "60_monitoreo_arriba")
        a_la_vista(page, page.get_by_text("Por calificación").first, 120)
        foto(page, "61_monitoreo_graficos")
        a_la_vista(page, page.get_by_text("Cuadro del informe").first, 60)
        foto(page, "62_monitoreo_cuadro")
        b = page.locator("button", has_text="resumen ejecutivo")
        a_la_vista(page, b, 300)
        b.click()
        page.get_by_text("Puntos clave").wait_for(timeout=240000)
        a_la_vista(page, page.get_by_text("Puntos clave"), 120)
        foto(page, "63_monitoreo_ejecutivo")
    mon_resumen()

    @paso("monitoreo normas")
    def mon_normas():
        ir(page, "/monitoreo/normas")
        foto(page, "64_mon_normas_arriba")
        t = page.locator("article").first
        a_la_vista(page, t, 30)
        foto(page, "65_mon_normas_tarjeta")
        foto(page, "66_mon_normas_tarjeta_sola", loc=t)
    mon_normas()

    @paso("monitoreo congreso")
    def mon_congreso():
        ir(page, "/monitoreo/congreso")
        foto(page, "67_mon_congreso_arriba")
        a_la_vista(page, page.get_by_text("Sección 2").first, 60)
        foto(page, "68_mon_congreso_senado")
    mon_congreso()

    @paso("monitoreo impacto")
    def mon_impacto():
        ir(page, "/monitoreo/impacto")
        foto(page, "69_mon_impacto_arriba")
        a_la_vista(page, page.get_by_text("Acciones por comité").first, 60)
        foto(page, "70_mon_impacto_comites")
    mon_impacto()

    @paso("monitoreo informe")
    def mon_informe():
        ir(page, "/monitoreo/informe")
        foto(page, "71_mon_informe_arriba")
        a_la_vista(page, page.get_by_text("Destinatarios del correo").first, 60)
        foto(page, "72_mon_informe_destinatarios")
    mon_informe()

    @paso("monitoreo busquedas guardadas")
    def mon_busquedas():
        ir(page, "/monitoreo/busquedas")
        foto(page, "73_mon_busquedas_arriba")
        f = page.locator("input[name=pregunta]")
        a_la_vista(page, f, 150)
        f.fill("cambios tributarios que afecten a las empresas mineras")
        page.locator("input[name=nombre]").fill(NOMBRE_BUSQUEDA)
        page.locator("select[name=frecuencia]").select_option("semanal")
        foto(page, "74_mon_busquedas_nueva")
        page.get_by_role("button", name="Crear búsqueda guardada").click()
        page.get_by_text(NOMBRE_BUSQUEDA).first.wait_for(timeout=150000)
        page.wait_for_load_state("networkidle")
        a_la_vista(page, page.get_by_text(NOMBRE_BUSQUEDA).first, 60)
        foto(page, "75_mon_busquedas_creada")
        page.get_by_role("button", name="Ejecutar ahora").first.click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Ejecutar ahora").first.wait_for(timeout=240000)
        page.wait_for_timeout(2000)
        ir(page, "/monitoreo/busquedas")
        page.get_by_role("link", name="Ver resultados").first.click()
        page.wait_for_load_state("networkidle")
        foto(page, "76_mon_busqueda_resultados")
        foto(page, "77_mon_busqueda_resultados_completo", completa=True)
    mon_busquedas()

    @paso("monitoreo usuarios")
    def mon_usuarios():
        ir(page, "/monitoreo/usuarios")
        foto(page, "78_mon_usuarios")
        foto(page, "79_mon_usuarios_completo", completa=True)
    mon_usuarios()

    nav.close()

# Limpieza: usuario temporal y la busqueda de ejemplo
try:
    cur.execute("SELECT id FROM busquedas_guardadas WHERE nombre = %s", (NOMBRE_BUSQUEDA,))
    for (bid,) in cur.fetchall():
        cur.execute("DELETE FROM busqueda_ejecuciones WHERE busqueda_id = %s", (bid,))
        cur.execute("DELETE FROM busquedas_guardadas WHERE id = %s", (bid,))
except Exception as e:  # noqa: BLE001
    nota(f"limpieza busqueda: {e}")
cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
with open(f"{SALIDA}/notas.txt", "w") as f:
    f.write("\n".join(notas))
for n in notas:
    print(f"::notice::{n}")
