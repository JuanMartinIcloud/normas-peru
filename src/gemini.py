"""Cliente minimo de la API de Google Gemini (capa gratuita) que devuelve JSON.

Variables de entorno:
    GEMINI_API_KEY   clave de Google AI Studio (obligatoria)
    GEMINI_MODELOS   modelos adicionales a probar al final, separados por coma (opcional)

Dos grupos de modelos, para no gastar en el trabajo automatico el cupo que necesita el usuario:
- FLASH (los mas precisos): para lo que lee el usuario (resumen diario). Si se agotan, se usan los Lite.
- LITE: para el trabajo automatico (filtro y analisis del monitoreo, recalificacion). Nunca usa Flash.
Cada consulta queda anotada en la tabla "uso_ia" (modelo y resultado) para medir el cupo real.
"""
import atexit
import json
import os
import re
import sys
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models"
FLASH = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview",
         "gemini-3.7-flash", "gemini-3.5-flash"]
LITE = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite-preview"]
# Reserva: se prueba al final si los anteriores agotaron su cupo del dia (no es Flash)
RESERVA = ["gemma-4-31b-it"]
TIMEOUT = 180
REINTENTOS = 4


class ErrorGemini(RuntimeError):
    pass


def _extra() -> list[str]:
    return [m.strip() for m in os.getenv("GEMINI_MODELOS", "").split(",") if m.strip() and not m.strip().startswith("gemini-2.5")]


def modelos() -> list[str]:
    """Para lo que lee el usuario: Flash primero; si se agotan, Lite."""
    return list(dict.fromkeys(FLASH + LITE + RESERVA + _extra()))


def modelos_lite() -> list[str]:
    """Para el trabajo automatico: solo Lite (y la reserva), nunca Flash."""
    return list(dict.fromkeys(LITE + RESERVA))


# --------------------------------------------------------------------------- registro de uso
_uso = []


def _registrar(modelo: str, resultado: str, http: int | None):
    """Anota cada consulta (se envia a la base al terminar la tarea o cada 50 consultas)."""
    _uso.append((ORIGEN, modelo, resultado, http))
    if len(_uso) >= 50:
        _enviar_uso()


def _enviar_uso():
    global _uso
    if not _uso:
        return
    lote, _uso = _uso, []
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return
    try:
        import psycopg2
        from psycopg2.extras import execute_values
        c = psycopg2.connect(url, connect_timeout=30)
        with c.cursor() as cur:
            cur.execute(SQL_USO)
            execute_values(cur, "INSERT INTO uso_ia (origen, modelo, resultado, http) VALUES %s", lote)
        c.commit()
        c.close()
    except Exception as e:  # noqa: BLE001  (el registro nunca debe detener la tarea)
        print(f"  (no se pudo anotar el uso de la IA: {type(e).__name__})")


SQL_USO = """CREATE TABLE IF NOT EXISTS uso_ia (
    id        BIGSERIAL PRIMARY KEY,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    origen    TEXT,
    modelo    TEXT NOT NULL,
    resultado TEXT NOT NULL,      -- ok | cupo (429) | error
    http      INTEGER)"""
ORIGEN = " ".join(os.path.basename(a) for a in sys.argv[:2])[:60]
atexit.register(_enviar_uso)


def verificar_clave() -> None:
    """Falla de inmediato, con instrucciones, si no esta configurada la clave."""
    _clave()


def _clave() -> str:
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        raise ErrorGemini(
            "Falta el secreto GEMINI_API_KEY. En GitHub: Settings > Secrets and variables > "
            "Actions > New repository secret, nombre GEMINI_API_KEY y como valor la clave de Google."
        )
    return clave


def _texto_respuesta(datos: dict) -> str:
    candidatos = datos.get("candidates") or []
    if not candidatos:
        motivo = (datos.get("promptFeedback") or {}).get("blockReason", "sin candidatos")
        raise ErrorGemini(f"Gemini no devolvio respuesta ({motivo})")
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    # Las partes marcadas como "thought" son el razonamiento interno del modelo, no la respuesta
    texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
    if not texto.strip():
        raise ErrorGemini(f"Respuesta vacia (finishReason={candidatos[0].get('finishReason')})")
    return texto


def es_limite_diario(texto: str) -> bool:
    """True si el "cupo agotado" (HTTP 429) es el limite del dia; False si es el limite por minuto."""
    return bool(re.search(r"PerDay|per day|daily", texto or "", re.I))


def espera_sugerida(texto: str) -> int:
    """Segundos que Google pide esperar (retryDelay), entre 5 y 65."""
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', texto or "")
    return max(5, min(65, int(float(m.group(1))) + 2)) if m else 30


def _a_json(texto: str):
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)  # por si viene entre ``` ```
    try:
        return json.loads(texto)
    except ValueError:
        a, b = texto.find("{"), texto.rfind("}")   # por si el modelo agrego texto alrededor
        if a < 0 or b <= a:
            raise
        return json.loads(texto[a:b + 1])


def _para_gemma(cuerpo: dict) -> dict:
    """Los modelos Gemma no aceptan instrucciones de sistema ni modo JSON: van dentro del mensaje."""
    instr = cuerpo["systemInstruction"]["parts"][0]["text"]
    partes = [dict(p) for p in cuerpo["contents"][0]["parts"]]
    partes[0]["text"] = (instr + "\n\nResponde UNICAMENTE con un objeto JSON valido, sin texto adicional.\n\n"
                         + partes[0].get("text", ""))
    return {"contents": [{"role": "user", "parts": partes}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": cuerpo["generationConfig"]["maxOutputTokens"]}}


def generar_json(instrucciones: str, contenido: str, esquema: dict, lista_modelos: list[str] | None = None,
                max_tokens: int = 16384) -> tuple[dict, str]:
    """Pide a Gemini una respuesta JSON que siga 'esquema'. Devuelve (datos, modelo_usado)."""
    clave = _clave()
    cuerpo = {
        "systemInstruction": {"parts": [{"text": instrucciones}]},
        "contents": [{"role": "user", "parts": [{"text": contenido}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "responseSchema": esquema,
        },
    }
    errores = []
    hubo_400 = False
    # Primera vuelta con el esquema estricto; si algun modelo lo rechaza (HTTP 400),
    # segunda vuelta sin esquema (las instrucciones ya describen el formato).
    usar = lista_modelos or modelos()
    intentos = [(m, True) for m in usar] + [(m, False) for m in usar]
    for modelo, con_esquema in intentos:
        if not con_esquema:
            if not hubo_400:
                break
            cuerpo["generationConfig"].pop("responseSchema", None)
        for intento in range(1, REINTENTOS + 1):
            try:
                r = requests.post(
                    f"{API}/{modelo}:generateContent",
                    headers={"x-goog-api-key": clave, "Content-Type": "application/json"},
                    json=_para_gemma(cuerpo) if modelo.startswith("gemma") else cuerpo,
                    timeout=TIMEOUT,
                )
            except requests.RequestException as e:
                errores.append(f"{modelo}: {e}")
                _registrar(modelo, "error", None)
                time.sleep(10 * intento)
                continue
            if r.status_code == 429:
                # Google limita por minuto y por dia. Por minuto: se espera lo que Google indica y se reintenta
                # el mismo modelo. Por dia: ese modelo ya no responde hasta manana, se pasa al siguiente.
                if es_limite_diario(r.text):
                    _registrar(modelo, "cupo_dia", 429)
                    errores.append(f"{modelo}: limite del dia")
                    break
                _registrar(modelo, "cupo_minuto", 429)
                time.sleep(espera_sugerida(r.text))
                continue
            _registrar(modelo, "ok" if r.status_code == 200 else "error", r.status_code)
            if r.status_code == 200:
                try:
                    return _a_json(_texto_respuesta(r.json())), modelo
                except (ValueError, ErrorGemini) as e:
                    errores.append(f"{modelo}: {e}")
                    time.sleep(5)
                    continue
            detalle = r.text[:300].replace("\n", " ")
            errores.append(f"{modelo}: HTTP {r.status_code} {detalle}")
            if r.status_code in (500, 502, 503, 504):
                time.sleep(15 * intento)   # servidor saturado: esperar y reintentar
                continue
            if r.status_code in (401, 403) and "API key" in r.text:
                raise ErrorGemini(f"La clave GEMINI_API_KEY no es valida: {detalle}")
            if r.status_code == 400 and "API key" in r.text:
                raise ErrorGemini(f"La clave GEMINI_API_KEY no es valida: {detalle}")
            if r.status_code == 400:
                hubo_400 = True
            break  # 400, 404 (modelo no existe), 429 (cupo agotado): pasar al siguiente modelo
    raise ErrorGemini("Ningun modelo respondio. " + " | ".join(errores[-6:]))
