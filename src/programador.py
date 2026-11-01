"""Programador de tareas: lanza cada tarea diaria a su hora y la repite si fallo.

Lo ejecuta el flujo "Programador de tareas" cada hora, solo en las horas en que hay tareas (una revision
rapida y termina). Es el unico
que lanza las tareas diarias: los flujos de esas tareas no tienen horario propio, asi ninguna corre dos
veces. Los horarios de GitHub pueden retrasarse; por eso cada tarea se lanza en la primera revision
posterior a su hora y, si falla, se repite en la revision siguiente (hasta 6 veces en el dia).

Tareas (hora de Lima):
  22:40  Descarga diaria de normas (diario.yml)
  23:30  Dias pendientes del historico de El Peruano (historico.yml)
  01:20  Proyectos de ley, seguimiento y leyes publicadas (congreso.yml)
  02:20  Monitoreo empresarial del mes y lo pedido desde la web (monitoreo.yml) -> listo antes de las 7:00
  03:20  Resumen diario con IA (resumen.yml)
  04:00  Texto completo de lo nuevo (indexar.yml)
  05:00  Busquedas guardadas que tocan hoy (busquedas.yml)
  05:30  Lectura de escaneados, si hay pendientes (ocr.yml)
  06:00  Alarma de consumo (vigilar.yml)
  15:00  Recalificacion pendiente del monitoreo, si hay (recalificar.yml)
  lunes 06:10  Vocabulario del corrector de busquedas (vocabulario.yml)
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

REPO = os.environ["GITHUB_REPOSITORY"]
API = f"https://api.github.com/repos/{REPO}/actions"
H = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
LIMA = timezone(timedelta(hours=-5))

TAREAS = [
    # (archivo, hora, minuto, inputs, depende_de, dia_de_semana o None)  (lunes = 0)
    ("diario.yml", 22, 40, {}, None, None),
    ("historico.yml", 23, 30, {}, None, None),
    ("congreso.yml", 1, 20, {}, None, None),
    ("monitoreo.yml", 2, 20, {"modo": "diario"}, "congreso.yml", None),
    ("resumen.yml", 3, 20, {}, None, None),
    ("indexar.yml", 4, 0, {}, "resumen.yml", None),
    ("busquedas.yml", 5, 0, {}, None, None),
    ("ocr.yml", 5, 30, {}, "indexar.yml", None),
    ("vigilar.yml", 6, 0, {}, None, None),
    ("recalificar.yml", 15, 0, {}, None, None),
    ("vocabulario.yml", 6, 10, {}, None, 0),
]
MAX_INTENTOS = 6            # por dia y por tarea
# La alarma de consumo "falla" a proposito cuando una base se acerca a su limite: no se repite (cada
# repeticion volveria a consultar todas las bases para dar el mismo aviso)
SIN_REPETIR = {"vigilar.yml"}
ESPERA_REINTENTO = timedelta(minutes=30)   # una falla se repite en la revision siguiente (cada hora)


def ahora():
    return datetime.now(LIMA)


def corridas(archivo, desde):
    """Ejecuciones de un flujo creadas desde 'desde' (sin contar las canceladas)."""
    r = requests.get(f"{API}/workflows/{archivo}/runs", headers=H, timeout=60,
                     params={"created": f">={desde.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ}", "per_page": 30})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return [x for x in r.json().get("workflow_runs", []) if x.get("conclusion") != "cancelled"]


def lanzar(archivo, inputs):
    r = requests.post(f"{API}/workflows/{archivo}/dispatches", headers=H, timeout=60,
                      json={"ref": "main", "inputs": inputs})
    print(f"{ahora():%Y-%m-%d %H:%M} lanzado {archivo} {inputs} -> HTTP {r.status_code}", flush=True)
    return r.status_code == 204


def hora_de_hoy(h, m):
    """Ultima vez que fueron las h:m (hoy o ayer, si todavia no llega esa hora hoy)."""
    n = ahora()
    t = n.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t <= n else t - timedelta(days=1)


def fallo(corrida):
    """True si algun trabajo de la ejecucion fallo (las tareas no se marcan como error: aqui se detecta)."""
    r = requests.get(f"{API}/runs/{corrida['id']}/jobs", headers=H, timeout=60, params={"per_page": 50})
    r.raise_for_status()
    return any(j.get("conclusion") not in ("success", "skipped") for j in r.json().get("jobs", []))


def revisar():
    for archivo, h, m, inputs, depende, dia_semana in TAREAS:
        desde = hora_de_hoy(h, m)
        if dia_semana is not None and desde.weekday() != dia_semana:
            continue
        if ahora() - desde > timedelta(hours=20):
            continue   # ya paso demasiado: le tocara en su proxima hora
        ya = corridas(archivo, desde)
        if ya is None:
            continue   # el flujo no existe
        if ya:
            # Ya corrio desde su hora. Si fallo, se repite (cada 30 min, hasta 6 veces en el dia).
            if any(x["status"] != "completed" for x in ya) or len(ya) >= MAX_INTENTOS or archivo in SIN_REPETIR:
                continue
            ultima = max(ya, key=lambda x: x["created_at"])
            fin = datetime.fromisoformat(ultima["updated_at"].replace("Z", "+00:00"))
            if ahora() - fin < ESPERA_REINTENTO or not fallo(ultima):
                continue
            print(f"{ahora():%H:%M} {archivo} tuvo una falla; se repite", flush=True)
            lanzar(archivo, inputs)
            continue
        if ahora() - desde > timedelta(hours=10):
            continue   # nunca corrio y ya paso demasiado: le tocara en su proxima hora
        if depende:
            previas = corridas(depende, desde - timedelta(hours=3)) or []
            en_curso = [x for x in previas if x["status"] != "completed"]
            if en_curso and ahora() - desde < timedelta(hours=2):
                continue   # espera a que termine lo anterior (maximo 2 horas)
        lanzar(archivo, inputs)


def main():
    try:
        revisar()
    except Exception as e:  # noqa: BLE001
        print(f"::warning title=Programador::{str(e)[:300]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
