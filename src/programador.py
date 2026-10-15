"""Programador propio de tareas (no depende de los horarios de GitHub, que pueden retrasarse horas).

Corre hasta ~5 h 45 min revisando cada 2 minutos la hora de Lima. Cuando a una tarea le toca y
todavia no corrio desde su hora, la lanza. Al terminar se vuelve a lanzar a si mismo.

Tareas (hora de Lima):
  22:40  Descarga diaria de normas (diario.yml)
  01:20  Proyectos de ley y seguimiento del Congreso (congreso.yml)
  02:20  Monitoreo empresarial del dia (monitoreo.yml, modo diario) -> listo antes de las 7:00
  03:20  Resumen diario con IA (resumen.yml)
  05:00  Busquedas guardadas que tocan hoy (busquedas.yml)
  06:00  Vocabulario y alarma de consumo
  09:00 a 20:00  Meses anteriores del monitoreo, sin limite de uno por dia
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

REPO = os.environ["GITHUB_REPOSITORY"]
API = f"https://api.github.com/repos/{REPO}/actions"
H = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
LIMA = timezone(timedelta(hours=-5))
DURACION = 5 * 3600 + 45 * 60
PAUSA = 120

TAREAS = [
    # (archivo, hora, minuto, inputs, depende_de)
    ("diario.yml", 22, 40, {}, None),
    ("congreso.yml", 1, 20, {}, None),
    ("monitoreo.yml", 2, 20, {"modo": "diario"}, "congreso.yml"),
    ("resumen.yml", 3, 20, {}, None),
    ("busquedas.yml", 5, 0, {}, None),
    ("vocabulario.yml", 6, 0, {}, None),
    ("vigilar.yml", 6, 5, {}, None),
]


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


def revisar():
    for archivo, h, m, inputs, depende in TAREAS:
        desde = hora_de_hoy(h, m)
        if ahora() - desde > timedelta(hours=10):
            continue   # ya paso demasiado: le tocara en su proxima hora
        ya = corridas(archivo, desde)
        if ya is None or ya:
            continue   # el flujo no existe, o ya corrio (o esta corriendo) desde su hora
        if depende:
            previas = corridas(depende, desde - timedelta(hours=3)) or []
            en_curso = [x for x in previas if x["status"] != "completed"]
            if en_curso and ahora() - desde < timedelta(hours=2):
                continue   # espera a que termine lo anterior (maximo 2 horas)
        lanzar(archivo, inputs)
    # Meses anteriores del monitoreo durante el dia, si no hay otro monitoreo en curso
    n = ahora()
    if 9 <= n.hour < 20:
        recientes = corridas("monitoreo.yml", n - timedelta(hours=6)) or []
        en_curso = any(x["status"] != "completed" for x in recientes)
        # Si una corrida de las ultimas 2 horas termino en menos de 10 minutos, no avanzo
        # (cupo de IA agotado o nada pendiente): no relanzar en vano.
        corta = False
        for x in recientes:
            try:
                ini = datetime.fromisoformat(x["run_started_at"].replace("Z", "+00:00"))
                fin = datetime.fromisoformat(x["updated_at"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            if n - fin < timedelta(hours=2) and fin - ini < timedelta(minutes=10):
                corta = True
        if not en_curso and not corta:
            lanzar("monitoreo.yml", {"modo": "historico", "forzar": "true"})


def main():
    inicio = time.time()
    while time.time() - inicio < DURACION:
        try:
            revisar()
        except Exception as e:  # noqa: BLE001
            print(f"aviso: {str(e)[:300]}", flush=True)
        time.sleep(PAUSA)
    lanzar("programador.yml", {})


if __name__ == "__main__":
    sys.exit(main())
