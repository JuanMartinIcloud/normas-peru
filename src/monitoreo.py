"""Monitoreo empresarial (reportes para AmCham Peru).

Para cada norma legal y cada proyecto de ley:
1. Filtro con IA (por lotes): ¿afecta al sector empresarial, a las empresas o al clima de inversion?
2. Para los relevantes, analisis con IA leyendo el texto completo: resumen, cambios a las normas
   vigentes, comentario de impacto, sector economico, calificacion (Favorable / Desfavorable /
   Para seguimiento), nivel de impacto, comites de AmCham involucrados y acciones sugeridas para
   cada comite y para el Directorio.
Todo queda en la tabla "analisis"; la web arma los reportes con ella.

    python src/monitoreo.py diario              # mes actual (solo lo que falta) + movimientos del Congreso
    python src/monitoreo.py historico           # el mes anterior al ultimo procesado (un mes por vez)
    python src/monitoreo.py rango 2026-08-01 2026-08-31
Opciones: --max-minutos 300
"""
import argparse
import os
import sys
import time
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import Json, execute_values

import db
import gemini
from textos import pdf_norma, texto_pdf

COMITES = [
    "Dispositivos Médicos", "Educación", "Facilitación de Comercio", "Infraestructura, Energía y Minería",
    "Minería", "Proveedores de Infraestructura Pasiva", "Salud", "Supply Chain Management",
    "Telecomunicaciones", "Turismo", "Asuntos Corporativos", "Asuntos Financieros", "Asuntos Jurídicos",
    "Asuntos Tributarios", "Desarrollo Sostenible", "Comunicación Interna", "Compliance",
    "Diversidad & Inclusión", "Gestión Humana", "Innovación", "Management Support", "Marketing",
]
SECTORES = [
    "Minería", "Hidrocarburos", "Electricidad", "Infraestructura y transporte", "Telecomunicaciones",
    "Financiero y seguros", "Comercio exterior y aduanas", "Agricultura y agroindustria", "Pesca",
    "Industria manufacturera", "Construcción e inmobiliario", "Salud y farmacéutico", "Educación",
    "Turismo", "Comercio y consumo", "Tecnología y economía digital", "Laboral", "Tributario",
    "Ambiental", "Contrataciones del Estado", "Transversal (todos los sectores)",
]
CALIFICACIONES = ["Favorable", "Desfavorable", "Para seguimiento"]
IMPACTOS = ["Alto", "Moderado", "Bajo"]

MODELOS_FILTRO = [m for m in os.getenv("MODELOS_FILTRO", "gemini-3.5-flash-lite,gemini-flash-latest,gemini-3.5-flash,gemini-flash-lite-latest").split(",") if m]
MODELOS_ANALISIS = None   # None = modelos por defecto (los mismos del buscador web)
# Los meses anteriores usan modelos distintos, para no gastar la cuota diaria del buscador ni del reporte diario
HIST_FILTRO = [m for m in os.getenv("HIST_FILTRO", "gemini-3.1-flash-lite,gemini-3.1-flash-lite-preview,gemini-3-flash-preview").split(",") if m]
HIST_ANALISIS = [m for m in os.getenv("HIST_ANALISIS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3-flash-preview").split(",") if m]
LOTE_FILTRO = 40
MAX_TEXTO = 25000

FILTRO_INSTR = """Eres analista de asuntos públicos de la Cámara de Comercio Americana del Perú (AmCham).
Recibes una lista de normas legales o proyectos de ley del Perú (id y descripción). Marca como
relevantes SOLO los que pueden afectar a las empresas privadas, a sectores económicos o al clima de
inversiones en el Perú: tributos, aduanas y comercio exterior, laboral, regulación sectorial (minería,
energía, hidrocarburos, telecomunicaciones, salud y medicamentos, transporte, financiero, agro, pesca,
turismo, educación privada), concesiones, APP e inversión pública relevante para privados,
contrataciones del Estado, competencia y consumidor, ambiental, datos y economía digital, permisos y
trámites, propiedad, arbitraje, compliance y anticorrupción empresarial.
NO son relevantes: designaciones, renuncias, encargos, viajes y licencias de funcionarios, actos
administrativos sobre personas concretas, saludos y reconocimientos, nombramientos de docentes o
jueces, asuntos internos de entidades sin efecto en privados, ordenanzas municipales menores
(nombres de calles, ceremonias), declaraciones de interés sin efecto económico.
Responde solo con el JSON pedido: "relevantes" = lista de los id relevantes."""

FILTRO_ESQUEMA = {"type": "OBJECT", "properties": {"relevantes": {"type": "ARRAY", "items": {"type": "STRING"}}},
                  "required": ["relevantes"]}


def _analisis_instr():
    return f"""Eres analista senior de asuntos públicos y regulatorios de la Cámara de Comercio Americana del
Perú (AmCham Perú). Analiza el documento (norma legal publicada o proyecto de ley) para el informe a
los comités y al Directorio. Escribe en español claro y sencillo, sin adornos, para lectores no abogados.
Usa solo lo que dice el documento; si no se puede saber algo, dilo. Responde solo con el JSON pedido:
- "resumen": 2 a 4 oraciones: en qué consiste.
- "cambios": qué cambia respecto de las normas vigentes (cita la ley o norma que modifica, deroga o
  reglamenta, si el documento lo indica); si crea algo nuevo, dilo.
- "comentario": 2 a 4 oraciones: cómo afecta al sector empresarial y al clima de inversiones en el Perú.
- "sector": el sector económico principal, uno de: {", ".join(SECTORES)}.
- "calificacion": "Favorable", "Desfavorable" o "Para seguimiento" (usa "Para seguimiento" cuando el
  impacto es moderado, incierto o depende de su reglamentación o aprobación).
- "impacto": "Alto", "Moderado" o "Bajo".
- "comites": los comités de AmCham a los que interesa (1 a 3), elegidos de esta lista exacta:
  {", ".join(COMITES)}.
- "acciones": para cada comité elegido, una acción concreta que debería realizar (por ejemplo: emitir
  opinión técnica, solicitar reunión con la comisión o el ministerio, preparar comentarios al
  reglamento, alertar a los asociados, monitorear su debate).
- "accion_directorio": acción recomendada al Directorio de AmCham (o "Ninguna por ahora")."""


ANALISIS_ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "resumen": {"type": "STRING"}, "cambios": {"type": "STRING"}, "comentario": {"type": "STRING"},
        "sector": {"type": "STRING"}, "calificacion": {"type": "STRING"}, "impacto": {"type": "STRING"},
        "comites": {"type": "ARRAY", "items": {"type": "STRING"}},
        "acciones": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "comite": {"type": "STRING"}, "accion": {"type": "STRING"}}, "required": ["comite", "accion"]}},
        "accion_directorio": {"type": "STRING"},
    },
    "required": ["resumen", "cambios", "comentario", "sector", "calificacion", "impacto", "comites",
                 "acciones", "accion_directorio"],
}


class Reloj:
    def __init__(self, minutos):
        self.fin = time.time() + minutos * 60

    def queda(self, margen=60):
        return time.time() < self.fin - margen


# --------------------------------------------------------------------------- textos completos

def _bases_texto():
    return [os.environ[k] for k in sorted(os.environ) if k.startswith("TEXTOS_URL_") and k != "TEXTOS_URL_4"
            and os.environ[k].strip()]


def textos(tipo, claves):
    """{clave: texto} desde las bases de texto (solo los que tienen texto)."""
    salida = {}
    if not claves:
        return salida
    for url in _bases_texto():
        try:
            c = psycopg2.connect(url, connect_timeout=60)
            cur = c.cursor()
            cur.execute("SELECT clave, left(texto, %s) FROM documentos WHERE tipo = %s AND clave = ANY(%s) AND estado = 'ok'",
                        (MAX_TEXTO, tipo, list(claves)))
            for k, t in cur.fetchall():
                salida[k] = t
            c.close()
        except psycopg2.Error as e:
            print(f"  base de texto no disponible: {str(e)[:100]}")
    return salida


# --------------------------------------------------------------------------- IA

def filtrar(items):
    """items: [(id, descripcion)] -> set de ids relevantes. None si la IA no responde."""
    relevantes = set()
    for i in range(0, len(items), LOTE_FILTRO):
        lote = items[i:i + LOTE_FILTRO]
        contenido = "\n".join(f"{k} | {d[:700]}" for k, d in lote)
        try:
            datos, _ = gemini.generar_json(FILTRO_INSTR, contenido, FILTRO_ESQUEMA, MODELOS_FILTRO, 4096)
        except gemini.ErrorGemini as e:
            print(f"  filtro sin respuesta: {str(e)[:200]}")
            return None if not relevantes and i == 0 else (relevantes, i)
        validos = {k for k, _ in lote}
        relevantes |= {str(x).strip() for x in datos.get("relevantes", []) if str(x).strip() in validos}
    return relevantes, len(items)


def _limpia(datos):
    def uno(v, opciones, defecto):
        v = str(v or "").strip()
        for o in opciones:
            if v.lower() == o.lower():
                return o
        return defecto
    if not isinstance(datos, dict):
        datos = datos[0] if isinstance(datos, list) and datos and isinstance(datos[0], dict) else {}
    comites = []
    for c in datos.get("comites") or []:
        for o in COMITES:
            if str(c).strip().lower() == o.lower() and o not in comites:
                comites.append(o)
    acciones = []
    for a in datos.get("acciones") or []:
        if not isinstance(a, dict):
            continue
        com = next((o for o in COMITES if str(a.get("comite", "")).strip().lower() == o.lower()), None)
        if com and a.get("accion"):
            acciones.append({"comite": com, "accion": str(a["accion"]).strip()})
            if com not in comites:
                comites.append(com)
    return {
        "resumen": str(datos.get("resumen") or "").strip(),
        "cambios": str(datos.get("cambios") or "").strip(),
        "comentario": str(datos.get("comentario") or "").strip(),
        "sector": uno(datos.get("sector"), SECTORES, "Transversal (todos los sectores)"),
        "calificacion": uno(datos.get("calificacion"), CALIFICACIONES, "Para seguimiento"),
        "impacto": uno(datos.get("impacto"), IMPACTOS, "Moderado"),
        "comites": comites,
        "acciones": acciones,
        "accion_directorio": str(datos.get("accion_directorio") or "").strip(),
    }


def analizar(cabecera, texto):
    contenido = cabecera + ("\n\nTEXTO COMPLETO:\n" + texto if texto else "\n\n(Sin texto completo; analiza con la sumilla.)")
    datos, modelo = gemini.generar_json(_analisis_instr(), contenido, ANALISIS_ESQUEMA, MODELOS_ANALISIS, 4096)
    return _limpia(datos), modelo


# --------------------------------------------------------------------------- base de datos

def guardar(filas):
    """filas: dicts con tipo, ref_id, fecha, relevante y (si relevante) los campos del analisis."""
    if not filas:
        return
    cols = ["tipo", "ref_id", "fecha", "relevante", "resumen", "cambios", "comentario", "sector",
            "calificacion", "impacto", "comites", "acciones", "accion_directorio", "lectura", "modelo"]
    valores = []
    for f in filas:
        v = [f.get(c) for c in cols]
        v[cols.index("acciones")] = Json(f["acciones"]) if f.get("acciones") is not None else None
        valores.append(v)
    c = db.conectar()
    with c.cursor() as cur:
        execute_values(cur, f"""INSERT INTO analisis ({', '.join(cols)}) VALUES %s
            ON CONFLICT (tipo, ref_id) DO UPDATE SET relevante = EXCLUDED.relevante, resumen = EXCLUDED.resumen,
              cambios = EXCLUDED.cambios, comentario = EXCLUDED.comentario, sector = EXCLUDED.sector,
              calificacion = EXCLUDED.calificacion, impacto = EXCLUDED.impacto, comites = EXCLUDED.comites,
              acciones = EXCLUDED.acciones, accion_directorio = EXCLUDED.accion_directorio,
              lectura = EXCLUDED.lectura, modelo = EXCLUDED.modelo""", valores)
    c.commit()
    c.close()


def consultar(sql, params=()):
    c = db.conectar()
    with c.cursor() as cur:
        cur.execute(sql, params)
        filas = cur.fetchall()
    c.commit()
    c.close()
    return filas


# --------------------------------------------------------------------------- proceso

def procesar_normas(desde, hasta, reloj):
    filas = consultar(
        """SELECT n.id, n.fecha, n.tipo, n.numero, n.entidad, n.sumilla, n.hash_unico, n.url_detalle
           FROM normas n WHERE n.fecha BETWEEN %s AND %s
             AND NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'N' AND a.ref_id = n.id)
           ORDER BY n.fecha DESC, n.id DESC""", (desde, hasta))
    print(f"Normas por revisar {desde} a {hasta}: {len(filas)}")
    hechas = 0
    for i in range(0, len(filas), 200):
        if not reloj.queda():
            break
        grupo = filas[i:i + 200]
        items = [(str(f[0]), f"{f[2]} {f[3] or ''} — {f[4] or ''}: {f[5] or ''}") for f in grupo]
        r = filtrar(items)
        if r is None:
            print("La IA no respondio al filtro; se continuara en la proxima ejecucion.")
            return hechas, False
        relevantes, cubiertos = r
        grupo = grupo[:cubiertos]
        no_rel = [{"tipo": "N", "ref_id": f[0], "fecha": f[1], "relevante": False} for f in grupo if str(f[0]) not in relevantes]
        guardar(no_rel)
        rel = [f for f in grupo if str(f[0]) in relevantes]
        txt = textos("N", [f[6] for f in rel])
        lote = []
        for f in rel:
            if not reloj.queda():
                break
            texto = txt.get(f[6])
            if not texto:
                try:
                    pdf = pdf_norma(f[7], f[1])
                    texto = texto_pdf(pdf, MAX_TEXTO) if pdf else ""
                except Exception:  # noqa: BLE001
                    texto = ""
            cab = (f"NORMA LEGAL publicada en El Peruano el {f[1]}\nTipo y número: {f[2]} {f[3] or ''}\n"
                   f"Entidad: {f[4] or ''}\nSumilla: {f[5] or ''}")
            try:
                datos, modelo = analizar(cab, texto[:MAX_TEXTO] if texto else "")
            except gemini.ErrorGemini as e:
                print(f"  analisis sin respuesta: {str(e)[:200]}")
                guardar(lote)
                return hechas, False
            lote.append({"tipo": "N", "ref_id": f[0], "fecha": f[1], "relevante": True, **datos,
                         "lectura": "texto completo" if texto else "sumilla", "modelo": modelo})
            hechas += 1
            if len(lote) >= 10:
                guardar(lote)
                lote = []
        guardar(lote)
        print(f"  {i + len(grupo)} normas revisadas, {hechas} analizadas")
        if cubiertos < len(filas[i:i + 200]):
            return hechas, False
    return hechas, True


def procesar_proyectos(desde, hasta, reloj):
    filas = consultar(
        """SELECT p.id, p.fecha_presentacion, p.numero, p.camara, p.proponente, p.autor, p.estado, p.titulo,
                  p.sumilla, p.periodo || '|' || p.camara || '|' || p.numero
           FROM proyectos_ley p
           WHERE NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'P' AND a.ref_id = p.id)
             AND (p.fecha_presentacion BETWEEN %s AND %s
                  OR EXISTS (SELECT 1 FROM seguimientos s WHERE s.proyecto_id = p.id
                               AND (s.fecha AT TIME ZONE 'America/Lima')::date BETWEEN %s AND %s
                               AND (s.estado ILIKE '%%dictamen%%' OR s.estado ILIKE '%%aut_grafa%%'
                                    OR s.estado ILIKE '%%senado%%')))
           ORDER BY p.fecha_presentacion DESC NULLS LAST""", (desde, hasta, desde, hasta))
    print(f"Proyectos por revisar {desde} a {hasta}: {len(filas)}")
    hechas = 0
    for i in range(0, len(filas), 200):
        if not reloj.queda():
            break
        grupo = filas[i:i + 200]
        items = [(str(f[0]), f"{f[7] or ''} — {(f[8] or '')[:400]}") for f in grupo]
        r = filtrar(items)
        if r is None:
            return hechas, False
        relevantes, cubiertos = r
        grupo = grupo[:cubiertos]
        fecha = lambda f: f[1] or desde  # noqa: E731
        guardar([{"tipo": "P", "ref_id": f[0], "fecha": fecha(f), "relevante": False}
                 for f in grupo if str(f[0]) not in relevantes])
        rel = [f for f in grupo if str(f[0]) in relevantes]
        txt = textos("P", [f[9] for f in rel])
        lote = []
        for f in rel:
            if not reloj.queda():
                break
            texto = txt.get(f[9]) or ""
            camara = {"D": "Cámara de Diputados", "S": "Senado", "C": "Congreso (unicameral)"}.get(f[3], f[3])
            cab = (f"PROYECTO DE LEY / PROPOSICIÓN LEGISLATIVA {f[2]} ({camara})\nPresentado: {f[1]}\n"
                   f"Proponente: {f[4] or ''}\nAutores: {(f[5] or '')[:300]}\nEstado: {f[6] or ''}\n"
                   f"Título: {f[7] or ''}\nSumilla: {f[8] or ''}")
            try:
                datos, modelo = analizar(cab, texto[:MAX_TEXTO])
            except gemini.ErrorGemini as e:
                print(f"  analisis sin respuesta: {str(e)[:200]}")
                guardar(lote)
                return hechas, False
            lote.append({"tipo": "P", "ref_id": f[0], "fecha": fecha(f), "relevante": True, **datos,
                         "lectura": "texto completo" if texto else "sumilla", "modelo": modelo})
            hechas += 1
            if len(lote) >= 10:
                guardar(lote)
                lote = []
        guardar(lote)
        print(f"  {i + len(grupo)} proyectos revisados, {hechas} analizados")
        if cubiertos < len(filas[i:i + 200]):
            return hechas, False
    return hechas, True


def leer_config(clave):
    f = consultar("SELECT valor FROM configuracion WHERE clave = %s", (clave,))
    return f[0][0] if f else None


def escribir_config(clave, valor):
    c = db.conectar()
    with c.cursor() as cur:
        cur.execute("""INSERT INTO configuracion (clave, valor) VALUES (%s, %s)
                       ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado = now()""", (clave, valor))
    c.commit()
    c.close()


def hoy_lima():
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def rango(desde, hasta, reloj):
    hn, ok1 = procesar_normas(desde, hasta, reloj)
    hp, ok2 = procesar_proyectos(desde, hasta, reloj)
    print(f"Rango {desde} a {hasta}: {hn} normas y {hp} proyectos analizados; completo={ok1 and ok2}")
    return ok1 and ok2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["diario", "historico", "rango"])
    ap.add_argument("fechas", nargs="*")
    ap.add_argument("--max-minutos", type=float, default=300)
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    reloj = Reloj(a.max_minutos)
    gemini.verificar_clave()
    db.conectar().close()   # aplica las etapas pendientes del esquema
    hoy = hoy_lima()
    if a.modo == "diario":
        inicio_mes = hoy.replace(day=1)
        rango(inicio_mes, hoy + timedelta(days=1), reloj)
        if leer_config("historico_hasta") is None:
            escribir_config("historico_hasta", inicio_mes.isoformat())
    elif a.modo == "historico":
        global MODELOS_FILTRO, MODELOS_ANALISIS
        MODELOS_FILTRO, MODELOS_ANALISIS = HIST_FILTRO, HIST_ANALISIS
        # Un mes por dia (salvo que se pida --forzar)
        if leer_config("historico_dia") == hoy.isoformat() and not a.forzar:
            print("Hoy ya se agrego un mes al historico.")
            return
        hasta_txt = leer_config("historico_hasta") or hoy.replace(day=1).isoformat()
        limite = date.fromisoformat(hasta_txt)          # primer dia del ultimo mes completo
        if limite <= date(2015, 1, 1):
            print("Historico completo desde 2015.")
            return
        fin = limite - timedelta(days=1)
        ini = fin.replace(day=1)
        if rango(ini, fin, reloj):
            escribir_config("historico_hasta", ini.isoformat())
            escribir_config("historico_dia", hoy.isoformat())
            print(f"Mes {ini:%Y-%m} completo.")
    else:
        rango(date.fromisoformat(a.fechas[0]), date.fromisoformat(a.fechas[1]), reloj)


if __name__ == "__main__":
    main()
