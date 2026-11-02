"""Control de calidad diario: comprueba con datos que todo este completo y correcto.

    python src/control.py

Cada comprobacion da OK, FALLA o INFO. El resultado se guarda en la tabla control_calidad (la web lo
muestra en Monitoreo > Control de calidad) y aparece como aviso en GitHub. Si hay alguna FALLA, la tarea
termina en rojo. Solo lee: no cambia nada.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import psycopg2
import requests

import bases
import db

LIMA = timezone(timedelta(hours=-5))
# Leyes que el Congreso da por publicadas y que El Peruano no lista (revisadas a mano, ver auditoria)
LEYES_SIN_PUBLICACION_CONOCIDAS = {"31632"}
SQL = """CREATE TABLE IF NOT EXISTS control_calidad (
    fecha     DATE PRIMARY KEY,
    ok        BOOLEAN NOT NULL,
    resultado JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now())"""

resultados = []


def anotar(estado, tema, detalle):
    resultados.append({"estado": estado, "tema": tema, "detalle": detalle})
    print(f"[{estado}] {tema}: {detalle}", flush=True)


def tareas(hoy):
    """Cada tarea de la noche corrio, termino bien y empezo cerca de su hora."""
    import programador as pr
    ahora = datetime.now(LIMA)
    for archivo, h, m, _inputs, _dep, dia in pr.TAREAS:
        hora = datetime.combine(hoy, datetime.min.time(), LIMA).replace(hour=h, minute=m)
        if hora > ahora:
            hora -= timedelta(days=1)   # tareas de la noche anterior (21:55, 22:40, 23:30) y de ayer por la tarde
        if dia is not None and hora.weekday() != dia:
            continue
        if ahora - hora < timedelta(minutes=40):
            continue   # todavia no le toca terminar
        corr = pr.corridas(archivo, hora) or []
        nombre = f"{archivo.replace('.yml', '')} ({h:02d}:{m:02d})"
        if not corr:
            anotar("FALLA", "Tarea no corrio", nombre)
            continue
        primera = min(corr, key=lambda x: x["created_at"])
        inicio = datetime.fromisoformat(primera["created_at"].replace("Z", "+00:00")).astimezone(LIMA)
        retraso = int((inicio - hora).total_seconds() // 60)
        en_curso = [x for x in corr if x["status"] != "completed"]
        ultima = max(corr, key=lambda x: x["created_at"])
        if en_curso:
            anotar("INFO", "Tarea en curso", f"{nombre}, empezo {inicio:%H:%M}")
        elif pr.fallo(ultima):
            anotar("FALLA", "Tarea con error", f"{nombre}, intentos: {len(corr)}")
        elif retraso > 120:
            anotar("FALLA", "Tarea muy atrasada", f"{nombre} empezo {inicio:%H:%M} ({retraso} min tarde)")
        else:
            anotar("OK", "Tarea", f"{nombre} empezo {inicio:%H:%M}" + (f" ({retraso} min despues de su hora)" if retraso > 30 else ""))


def main():
    hoy = datetime.now(LIMA).date()
    ayer = hoy - timedelta(days=1)
    try:
        tareas(hoy)
    except Exception as e:  # noqa: BLE001
        anotar("FALLA", "Revision de tareas", f"no se pudo consultar GitHub ({type(e).__name__})")

    c = db.conectar()   # aplica las etapas pendientes del esquema
    cur = c.cursor()

    def uno(sql, args=()):
        cur.execute(sql, args)
        return cur.fetchone()

    # Normas: el dia de ayer completo, comparado con El Peruano en este momento
    try:
        import elperuano
        for d in (ayer, ayer - timedelta(days=1)):
            est = uno("SELECT estado FROM descargas WHERE fecha = %s", (d,))
            (guardadas,) = uno("SELECT count(*) FROM normas WHERE fecha = %s", (d,))
            en_ep = len(elperuano.descargar_dia(d))
            if not est or est[0] not in ("ok", "vacio"):
                anotar("FALLA", "Normas", f"{d}: descarga no confirmada")
            elif guardadas < en_ep:
                anotar("FALLA", "Normas", f"{d}: el sistema tiene {guardadas} y El Peruano {en_ep}")
            else:
                anotar("OK", "Normas", f"{d}: {guardadas} normas, igual que El Peruano")
    except Exception as e:  # noqa: BLE001
        anotar("FALLA", "Normas", f"no se pudo comparar con El Peruano ({type(e).__name__})")

    # Proyectos de ley: totales por periodo y camara, comparados con el portal del Congreso
    try:
        import congreso
        nuestros = {(str(a), b): n for a, b, n in
                    (cur.execute("SELECT periodo, camara, count(*) FROM proyectos_ley GROUP BY 1, 2") or cur.fetchall())}
        for per in congreso.periodos():
            for cam in congreso.CAMARAS:
                datos = congreso._con_reintentos(congreso._s.post, f"{congreso.API}/proyecto-ley/lista-con-filtro",
                                                 json=congreso._cuerpo(per["perParId"], cam, 0))["data"]
                oficial = datos.get("rowsTotal") or 0
                propio = nuestros.get((str(per["perParId"]), cam), 0)
                if not oficial and not propio:
                    continue
                if propio < oficial:
                    anotar("FALLA", "Proyectos de ley", f"{per.get('desPerParAbrev')} {cam}: sistema {propio}, Congreso {oficial}")
                else:
                    anotar("OK", "Proyectos de ley", f"{per.get('desPerParAbrev')} {cam}: {propio}, igual que el Congreso")
    except Exception as e:  # noqa: BLE001
        c.rollback()
        anotar("FALLA", "Proyectos de ley", f"no se pudo comparar con el Congreso ({type(e).__name__})")

    # Leyes sin enlace a su publicacion en El Peruano
    try:
        cur.execute("SELECT DISTINCT ley_numero FROM proyectos_ley WHERE ley_numero IS NOT NULL AND ley_docs->'ley' IS NULL")
        sin = sorted({r[0] for r in cur.fetchall()} - LEYES_SIN_PUBLICACION_CONOCIDAS)
        anotar("FALLA" if sin else "OK", "Leyes enlazadas a El Peruano",
               f"sin enlace: {', '.join(sin[:20])}" if sin else "todas (salvo la Ley 31632, que El Peruano no lista)")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Leyes sin enlace a su publicacion en El Peruano", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    # Monitoreo
    try:
        (vacios,) = uno("""SELECT count(*) FROM analisis WHERE relevante AND NOT excluido AND
                           (coalesce(resumen, '') = '' OR coalesce(cardinality(comites), 0) = 0 OR calificacion IS NULL OR puntaje IS NULL)""")
        anotar("FALLA" if vacios else "OK", "Analisis del reporte completos", f"{vacios} incompletos" if vacios else "todos completos")
        inicio_mes = hoy.replace(day=1)
        (faltan_n,) = uno("""SELECT count(*) FROM normas n WHERE n.fecha BETWEEN %s AND %s
                             AND NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'N' AND a.ref_id = n.id)""", (inicio_mes, ayer))
        (faltan_p,) = uno("""SELECT count(*) FROM proyectos_ley p WHERE p.fecha_presentacion BETWEEN %s AND %s
                             AND NOT EXISTS (SELECT 1 FROM analisis a WHERE a.tipo = 'P' AND a.ref_id = p.id)""", (inicio_mes, ayer))
        if inicio_mes <= ayer:
            anotar("FALLA" if faltan_n or faltan_p else "OK", "Monitoreo del mes en curso",
                   f"sin revisar hasta ayer: {faltan_n} normas y {faltan_p} proyectos" if faltan_n or faltan_p else "revisado hasta ayer")
        (meses_ok, meses_total) = uno("""SELECT count(*) FILTER (WHERE r = t), count(*) FROM (
                                        SELECT to_char(n.fecha, 'YYYY-MM') m, count(*) t, count(a.id) r FROM normas n
                                        LEFT JOIN analisis a ON a.tipo = 'N' AND a.ref_id = n.id GROUP BY 1) x""")
        anotar("INFO", "Monitoreo de meses anteriores", f"{meses_ok} de {meses_total} meses revisados por completo")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Monitoreo", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    # Resumen diario de ayer
    try:
        anotar("OK" if uno("SELECT 1 FROM resumenes WHERE fecha = %s", (ayer,)) else "FALLA", "Resumen diario", f"{ayer}")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Resumen diario de ayer", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    # Texto completo de las normas de la ultima semana (hasta anteayer)
    try:
        cur.execute("SELECT hash_unico FROM normas WHERE fecha BETWEEN %s AND %s AND url_detalle IS NOT NULL",
                    (hoy - timedelta(days=8), hoy - timedelta(days=2)))
        claves = {r[0] for r in cur.fetchall()}
        halladas = set()
        for _, url in bases.bases_texto():
            try:
                t = psycopg2.connect(url, connect_timeout=60)
                tc = t.cursor()
                tc.execute("SELECT clave FROM documentos WHERE tipo = 'N' AND clave = ANY(%s)", (list(claves),))
                halladas |= {r[0] for r in tc.fetchall()}
                t.close()
            except psycopg2.Error:
                pass
        faltan = len(claves - halladas)
        anotar("FALLA" if faltan else "OK", "Texto completo (ultima semana)",
               f"{faltan} de {len(claves)} normas sin texto guardado" if faltan else f"las {len(claves)} normas tienen su texto")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Texto completo de las normas de la ultima semana (hasta ante", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    # Clasificacion
    try:
        (otros, sin_rubro, pend_ia) = uno("""SELECT count(*) FILTER (WHERE sector = 'Otros'), count(*) FILTER (WHERE rubro = 'Sin clasificar'),
                                             count(*) FILTER (WHERE rubro = 'Sin clasificar' AND NOT rubro_ia) FROM normas""")
        anotar("INFO", "Clasificacion", f"sector 'Otros': {otros}; sin rubro: {sin_rubro} (por revisar con IA: {pend_ia})")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Clasificacion", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    # Uso de la IA de ayer y cupo de Neon
    try:
        try:
            cur.execute("""SELECT modelo, count(*) FILTER (WHERE resultado = 'ok'), count(*) FILTER (WHERE resultado = 'cupo_dia')
                           FROM uso_ia WHERE creado_en >= now() - interval '24 hours' GROUP BY 1 ORDER BY 2 DESC""")
            filas = cur.fetchall()
            anotar("INFO", "IA (ultimas 24 horas)", "; ".join(f"{m}: {ok}" + (" (llego a su limite del dia)" if d else "")
                                                              for m, ok, d in filas) or "sin consultas")
        except psycopg2.Error:
            c.rollback()
        try:
            ctl = psycopg2.connect(bases.control_url(), connect_timeout=60)
            cc = ctl.cursor()
            cc.execute("""SELECT base, round(transferido / 1e9, 2) FROM cupos
                          WHERE periodo >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' ORDER BY transferido DESC LIMIT 3""")
            filas = cc.fetchall()
            ctl.close()
            mayor = max((float(g) for _, g in filas), default=0)
            anotar("FALLA" if mayor >= 4 else "OK", "Transferencia de Neon este mes",
                   "; ".join(f"{b}: {g} GB de 5" for b, g in filas) or "sin medicion")
        except Exception as e:  # noqa: BLE001
            anotar("FALLA", "Transferencia de Neon", f"no se pudo leer ({type(e).__name__})")
    except Exception as e:  # noqa: BLE001  (una comprobacion que falla no detiene las demas)
        c.rollback()
        anotar("FALLA", "Uso de la IA de ayer y cupo de Neon", f"no se pudo comprobar ({type(e).__name__}: {str(e)[:120]})")

    ok = not any(r["estado"] == "FALLA" for r in resultados)
    cur.execute(SQL)
    cur.execute("""INSERT INTO control_calidad (fecha, ok, resultado) VALUES (%s, %s, %s)
                   ON CONFLICT (fecha) DO UPDATE SET ok = EXCLUDED.ok, resultado = EXCLUDED.resultado, creado_en = now()""",
                (hoy, ok, json.dumps(resultados, ensure_ascii=False)))
    c.commit()
    c.close()
    fallas = [r for r in resultados if r["estado"] == "FALLA"]
    texto = (f"TODO CORRECTO ({len(resultados)} comprobaciones)" if ok else
             f"{len(fallas)} FALLAS: " + " | ".join(f"{r['tema']}: {r['detalle']}" for r in fallas))
    print(f"::{'notice' if ok else 'error'} title=Control de calidad {hoy}::{texto[:3000]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
