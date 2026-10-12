"""Clasificacion por reglas (gratis): sector segun la entidad emisora, rubro segun palabras clave."""
import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).lower().strip()


# (sector, palabras clave que aparecen en el nombre de la entidad)
SECTORES = [
    ("Congreso", ["congreso de la republica"]),
    ("Presidencia y PCM", ["presidencia del consejo de ministros", "presidencia de la republica", "pcm"]),
    ("Economia y Finanzas", ["economia y finanzas", "mef", "sunat", "sbs", "superintendencia de banca"]),
    ("Salud", ["salud", "minsa", "essalud", "digesa", "digemid", "sunasa"]),
    ("Educacion", ["educacion", "minedu", "sunedu", "sineace"]),
    ("Justicia y Derechos Humanos", ["justicia", "minjus", "inpe", "ministerio publico", "poder judicial", "defensoria"]),
    ("Interior", ["del interior", "mininter", "policia nacional", "migraciones"]),
    ("Defensa", ["defensa", "mindef", "fuerzas armadas", "ejercito", "marina de guerra", "fuerza aerea"]),
    ("Relaciones Exteriores", ["relaciones exteriores", "rree"]),
    ("Energia y Minas", ["energia y minas", "minem", "osinergmin", "ingemmet", "perupetro"]),
    ("Transportes y Comunicaciones", ["transportes y comunicaciones", "mtc", "osiptel", "sutran", "ositran", "indecopi"]),
    ("Vivienda y Construccion", ["vivienda", "construccion y saneamiento", "sunass", "sedapal"]),
    ("Agricultura y Riego", ["agricultura", "midagri", "senasa", "sernanp", "agua", "ana "]),
    ("Ambiente", ["del ambiente", "minam", "oefa", "senace"]),
    ("Produccion", ["de la produccion", "produce", "sanipes", "pesquer"]),
    ("Comercio Exterior y Turismo", ["comercio exterior", "mincetur", "promperu", "turismo"]),
    ("Trabajo y Promocion del Empleo", ["trabajo y promocion del empleo", "mtpe", "sunafil", "essalud"]),
    ("Mujer y Poblaciones Vulnerables", ["mujer y poblaciones vulnerables", "mimp"]),
    ("Desarrollo e Inclusion Social", ["desarrollo e inclusion social", "midis", "pension 65"]),
    ("Cultura", ["ministerio de cultura", "cultura"]),
    ("Organismos Autonomos", ["jne", "jurado nacional de elecciones", "onpe", "reniec", "contraloria", "tribunal constitucional", "banco central"]),
    ("Gobiernos Regionales", ["gobierno regional"]),
    ("Gobiernos Locales", ["municipalidad", "gobierno local"]),
]

# (rubro, palabras clave en sumilla o tipo)
RUBROS = [
    ("Tributario y Aduanero", ["tribut", "impuesto", "arancel", "aduan", "igv", "renta", "sunat", "uit"]),
    ("Presupuesto y Finanzas Publicas", ["presupuesto", "credito suplementario", "transferencia de partidas", "endeudamiento", "tesoro publico"]),
    ("Contrataciones del Estado", ["contrataciones del estado", "osce", "licitacion", "adquisiciones"]),
    ("Personal y Designaciones", ["designa", "designacion", "encargan", "acepta renuncia", "da por concluida", "nombra", "cesa", "autorizan viaje"]),
    ("Salud", ["salud", "sanitari", "hospital", "medicament", "vacuna", "epidemi"]),
    ("Educacion", ["educacion", "escuela", "universidad", "docente", "colegio", "curricul"]),
    ("Laboral y Seguridad Social", ["laboral", "trabajador", "pension", "remuneracion", "seguridad social", "empleo"]),
    ("Seguridad y Defensa", ["seguridad ciudadana", "policia", "defensa nacional", "estado de emergencia", "orden interno"]),
    ("Justicia y Penal", ["penal", "judicial", "delito", "carcel", "penitenciar", "codigo procesal"]),
    ("Medio Ambiente y Recursos Naturales", ["ambient", "residuos", "forestal", "biodiversidad", "cambio climatico", "agua", "area natural protegida"]),
    ("Energia y Minería", ["energia", "electric", "hidrocarburo", "mineria", "minero", "gas natural", "petroleo"]),
    ("Transportes e Infraestructura", ["transporte", "carretera", "vial", "puerto", "aeropuerto", "ferrocarril", "infraestructura"]),
    ("Vivienda y Saneamiento", ["vivienda", "saneamiento", "agua potable", "alcantarillado", "urbano"]),
    ("Agricultura y Pesca", ["agrari", "agricol", "pesquer", "pesca", "riego", "ganader"]),
    ("Comercio, Industria y Turismo", ["comercio", "industria", "turismo", "exporta", "mype", "empresa"]),
    ("Telecomunicaciones y Digital", ["telecomunicaciones", "digital", "internet", "datos personales", "firma electronica"]),
    ("Desarrollo Social", ["inclusion social", "programa social", "vulnerable", "pobreza", "mujer", "discapacidad"]),
    ("Cultura y Patrimonio", ["patrimonio cultural", "cultura", "monumento", "declara de interes nacional"]),
    ("Elecciones y Organizacion del Estado", ["elector", "elecciones", "reglamento de organizacion", "rof", "organizacion y funciones"]),
    ("Relaciones Exteriores", ["tratado", "convenio internacional", "embajad", "consul"]),
]


def clasificar_sector(entidad: str) -> str:
    e = _norm(entidad)
    for sector, claves in SECTORES:
        if any(c in e for c in claves):
            return sector
    return "Otros"


def clasificar_rubro(sumilla: str, tipo: str = "") -> str:
    t = _norm(f"{tipo} {sumilla}")
    for rubro, claves in RUBROS:
        if any(c in t for c in claves):
            return rubro
    return "Sin clasificar"


def clasificar(entidad: str, sumilla: str, tipo: str = "") -> dict:
    return {
        "sector": clasificar_sector(entidad),
        "rubro": clasificar_rubro(sumilla, tipo),
    }
