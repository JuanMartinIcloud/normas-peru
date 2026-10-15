"""Cliente minimo de la API de Google Gemini (capa gratuita) que devuelve JSON.

Variables de entorno:
    GEMINI_API_KEY   clave de Google AI Studio (obligatoria)
    GEMINI_MODELOS   modelos a probar en orden, separados por coma (opcional)

Por defecto usa 'gemini-flash-latest', un alias que Google mantiene apuntando a su
modelo Flash vigente; si falla (cupo agotado, modelo retirado), prueba los siguientes.
"""
import json
import os
import re
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models"
MODELOS_POR_DEFECTO = "gemini-flash-latest,gemini-3.5-flash-lite,gemini-3.5-flash"
# Reserva: se prueban al final si los anteriores agotaron su cupo del dia
RESERVA = ["gemini-flash-lite-latest", "gemma-4-31b-it"]
TIMEOUT = 180
REINTENTOS = 4


class ErrorGemini(RuntimeError):
    pass


def modelos() -> list[str]:
    texto = os.getenv("GEMINI_MODELOS", "").strip() or MODELOS_POR_DEFECTO
    lista = [m.strip() for m in texto.split(",") if m.strip() and not m.strip().startswith("gemini-2.5")]
    return lista + [m for m in RESERVA if m not in lista]


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
                time.sleep(10 * intento)
                continue
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
