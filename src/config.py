"""Configuracion central. Todo se puede sobreescribir con variables de entorno."""
import os

BASE_URL = "https://diariooficial.elperuano.pe"

# Endpoint que devuelve las normas de un rango de fechas.
# PENDIENTE DE CONFIRMAR con src/probe.py (la pagina carga el listado por AJAX).
ENDPOINT = os.getenv("ELPERUANO_ENDPOINT", f"{BASE_URL}/Normas/ObtenerNormas")

# GET o POST, y nombres de los parametros de fecha (ajustar tras el sondeo)
METODO = os.getenv("ELPERUANO_METODO", "POST").upper()
PARAM_DESDE = os.getenv("ELPERUANO_PARAM_DESDE", "fechaInicio")
PARAM_HASTA = os.getenv("ELPERUANO_PARAM_HASTA", "fechaFin")
FORMATO_FECHA = os.getenv("ELPERUANO_FORMATO_FECHA", "%Y-%m-%d")

# Equivalencias de nombres de campo si la respuesta es JSON (ajustar tras el sondeo)
CAMPOS = {
    "tipo": ["tipo", "tipoNorma", "TipoNorma"],
    "numero": ["numero", "numeroNorma", "NumeroNorma", "nroNorma"],
    "entidad": ["entidad", "sector", "institucion", "Entidad", "Sector"],
    "sumilla": ["sumilla", "Sumilla", "descripcion", "titulo"],
    "url_pdf": ["urlPdf", "pdf", "url", "linkPdf", "rutaPdf"],
    "extraordinaria": ["extraordinaria", "edicionExtraordinaria", "esExtraordinaria"],
}

# Cortesia con el servidor: segundos de espera entre solicitudes
PAUSA_SEGUNDOS = float(os.getenv("PAUSA_SEGUNDOS", "1.5"))
REINTENTOS = int(os.getenv("REINTENTOS", "4"))
TIMEOUT = int(os.getenv("TIMEOUT", "40"))

USER_AGENT = os.getenv(
    "USER_AGENT", "Mozilla/5.0 (compatible; normas-peru-research/0.1; uso academico)"
)

DATABASE_URL = os.getenv("DATABASE_URL", "")  # cadena de conexion de Neon
