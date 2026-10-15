"""Sondeo: cobertura por camara del periodo 2026 y estructura del seguimiento de un expediente."""
import json, sys
sys.path.insert(0, "src")
import congreso
from textos import API_CONGRESO, CABECERAS_CONGRESO, cifrar
import requests

pers = congreso.periodos()
print("PERIODOS:", [(p["perParId"], p.get("desPerParAbrev")) for p in pers][:6])
for per in pers[:2]:
    for cam in ["C", "D", "S"]:
        d = congreso._con_reintentos(congreso._s.post, f"{congreso.API}/proyecto-ley/lista-con-filtro",
                                     json=congreso._cuerpo(per["perParId"], cam, 0))["data"]
        lote = d.get("proyectos") or []
        print("LISTA", per["perParId"], cam, "total", d.get("rowsTotal"), "ej:", [(p.get("proyectoLey"), p.get("codTipoParl"), p.get("fecPresentacion"), p.get("desEstado")) for p in lote[:3]])
        if lote and cam == "S":
            print("CAMPOS", sorted(lote[0].keys()))
# expediente de un proyecto con dictamen
def exp(periodo, num, cam):
    r = requests.get(f"{API_CONGRESO}/expediente/{cifrar(periodo)}/{cifrar(num)}", params={"codTipoParl": cam}, headers=CABECERAS_CONGRESO, timeout=60)
    return r.json().get("data") or {}
for periodo, num, cam in [("2021", "1", "C"), ("2026", "1", "D"), ("2026", "1", "S")]:
    try:
        e = exp(periodo, num, cam)
        print("EXP", periodo, num, cam, "claves", sorted(e.keys()))
        segs = e.get("seguimientos") or []
        print("  n seguimientos", len(segs))
        for s in segs[:40]:
            print("  SEG", json.dumps({k: s.get(k) for k in s if k != "archivos"}, ensure_ascii=False)[:400])
        print("  GENERAL", json.dumps(e.get("general"), ensure_ascii=False)[:600])
    except Exception as ex:
        print("EXP error", periodo, num, cam, ex)
