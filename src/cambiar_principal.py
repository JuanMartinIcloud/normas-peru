"""Rota la base principal entre varias copias para repartir el cupo de transferencia de Neon.

    python src/cambiar_principal.py            # decide solo (lo corre "Cupos de Neon" cada hora)
    python src/cambiar_principal.py --forzar   # cambia ahora a la que menos gasto (flujo "Cambiar base principal")

Cada proyecto gratuito de Neon puede enviar 5 GB al mes. Las bases principales posibles son la 4, 9, 10 y
11 (y las que el sistema cree solo). Regla:
- Primera vuelta: cuando la activa llega a 2 GB en el mes, se copia TODO a la que menos gasto y el sistema
  (web y tareas) pasa a usarla.
- Cuando todas pasaron los 2 GB, se sigue rotando: se cambia cuando la activa supera en 1,5 GB a la que
  menos gasto (asi cada una llega a unos 3,8 GB como maximo).
- Si ninguna puede recibirla (todas gastaron demasiado), se crea una base nueva en Neon y se pasa a esa.
- La copia gasta de la activa lo que pesan sus datos (unos 0,3 GB). Se hace de madrugada (0 a 5 a. m. de
  Lima), salvo que la activa ya pase de 3,5 GB: entonces se hace en ese momento. Nunca se copia si la copia
  dejaria la activa por encima de 4,8 GB.
- Mientras se copia, las tareas automaticas esperan (estado "copiando"); la web sigue leyendo la activa.
- Antes de cambiar se verifica que las dos bases tengan las mismas filas en cada tabla. Si algo falla,
  el sistema sigue con la base de siempre y nada se pierde.
- El dia 1 de cada mes Neon renueva el cupo de todas y la rotacion empieza de nuevo.
"""
import argparse
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone

import psycopg2
import requests

import bases_auto
import cupos
import principal

GB = 10 ** 9
PRIMERA_VUELTA = 2 * GB          # la activa cambia al llegar a 2 GB
DIFERENCIA = int(1.5 * GB)       # ...si la otra gasto al menos 1,5 GB menos
TOPE_DESTINO = int(3.0 * GB)     # una base que ya gasto 3 GB no recibe la copia
URGENTE_BYTES = int(3.5 * GB)    # desde aqui se cambia a cualquier hora (no se espera la madrugada)
NUEVA_DESDE = int(3.0 * GB)      # si la activa pasa de 3 GB y no hay a donde ir, se crea una base nueva
COPIA_BYTES = int(0.35 * GB)     # lo que gasta copiar la base (sus datos pesan unos 0,3 GB; con margen)
LIMITE_SEGURO = int(4.8 * GB)    # la copia nunca debe dejar la base activa por encima de esto
IMAGEN = "postgres:18"


def transferido(n):
    cupos._cache["t"] = 0   # medicion fresca
    return cupos.medidos().get(cupos.host(principal.url_de(n)), 0)


def marcar(estado, activa=None, detalle=None):
    c = psycopg2.connect(principal.control_url(), connect_timeout=60)
    with c.cursor() as cur:
        cur.execute(principal.SQL)
        cur.execute("INSERT INTO principal (id, activa) VALUES (1, 4) ON CONFLICT (id) DO NOTHING")
        if activa is None:
            cur.execute("UPDATE principal SET estado = %s, detalle = coalesce(%s, detalle) WHERE id = 1", (estado, detalle))
        else:
            cur.execute("UPDATE principal SET estado = %s, activa = %s, cambiado_en = now(), detalle = %s WHERE id = 1",
                        (estado, activa, detalle))
    c.commit()
    c.close()
    principal._cache["t"] = 0


def tareas_en_curso():
    """Otras ejecuciones de GitHub Actions en curso (para no copiar mientras escriben en la base)."""
    token, repo, propio = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_RUN_ID")
    if not token or not repo:
        return []
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/runs", params={"status": "in_progress", "per_page": 50},
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=60)
        r.raise_for_status()
        return [x["name"] for x in r.json().get("workflow_runs", []) if str(x["id"]) != str(propio)]
    except requests.RequestException as e:
        print(f"  (no se pudo consultar las tareas en curso: {e})")
        return []


def docker(args, url):
    return subprocess.run(["docker", "run", "--rm", "-e", "URL", "-v", f"{TMP}:/x", IMAGEN, "sh", "-c", args],
                          env={**os.environ, "URL": url}, capture_output=True, text=True)


def vaciar(url):
    """Borra las tablas de la base de destino (la que no esta en uso) antes de copiar."""
    c = psycopg2.connect(url, connect_timeout=60)
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for (t,) in cur.fetchall():
            cur.execute(f'DROP TABLE IF EXISTS public."{t}" CASCADE')
        cur.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'")
        for (s,) in cur.fetchall():
            cur.execute(f'DROP SEQUENCE IF EXISTS public."{s}" CASCADE')
    c.close()


def conteos(url):
    c = psycopg2.connect(url, connect_timeout=60)
    salida = {}
    with c.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
        for (t,) in cur.fetchall():
            cur.execute(f'SELECT count(*) FROM public."{t}"')
            salida[t] = cur.fetchone()[0]
        cur.execute("SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'public'")
        for s, v in cur.fetchall():
            salida[f"secuencia {s}"] = v
    c.close()
    return salida


def copiar(origen, destino):
    subprocess.run(["docker", "pull", "-q", IMAGEN], check=True, capture_output=True)
    r = docker('pg_dump --no-owner --no-privileges -Fc -f /x/p.dump "$URL"', origen)
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo leer la base activa: {r.stderr[-800:]}")
    print(f"  copia leida: {os.path.getsize(os.path.join(TMP, 'p.dump')) / 1e6:.0f} MB comprimidos")
    # Sin los comentarios de las extensiones (solo el administrador de Neon puede escribirlos)
    r = docker("pg_restore -l /x/p.dump | grep -v 'COMMENT - EXTENSION' > /x/lista", origen)
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo preparar la copia: {r.stderr[-800:]}")
    vaciar(destino)
    r = docker('pg_restore --no-owner --no-privileges --single-transaction -L /x/lista -d "$URL" /x/p.dump', destino)
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo escribir en la otra base: {r.stderr[-1500:]}")


def elegir_destino(act):
    """(numero, transferido) de la base principal que menos gasto este mes, sin contar la activa."""
    otras = [(n, transferido(n)) for n in principal.principales() if n != act and principal.url_de(n)]
    return min(otras, key=lambda x: x[1]) if otras else (None, None)


def main():
    global TMP
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    if not principal.control_url():
        raise SystemExit("Falta el secreto TEXTOS_URL_2 (base de control).")
    bases_auto.registrar_fijas()
    act, estado = principal.leer(estricto=True)
    b_act = transferido(act)
    otra, b_otra = elegir_destino(act)
    resumen = ", ".join(f"{n}: {transferido(n) / GB:.2f} GB" for n in principal.principales())
    print(f"Base principal activa: {principal.nombre(act)} con {b_act / GB:.2f} GB transferidos este mes. "
          f"Todas las principales: {resumen}.")
    if b_act + COPIA_BYTES > LIMITE_SEGURO:
        print(f"::warning title=Base principal::La activa ya va en {b_act / GB:.2f} GB: copiarla ahora la llevaria "
              "cerca del limite de 5 GB. No se copia; sigue la emergencia (solo la web) hasta que se renueve el cupo.")
        return
    if estado == "copiando":
        print("Habia una copia sin terminar (la tarea anterior se corto): se vuelve a intentar.")
    elif not a.forzar:
        necesita = b_act >= PRIMERA_VUELTA and (otra is None or b_act - b_otra >= DIFERENCIA or b_otra >= TOPE_DESTINO)
        if not necesita:
            print("No hace falta cambiar.")
            return
        hora = (datetime.now(timezone.utc) - timedelta(hours=5)).hour
        if b_act < URGENTE_BYTES and not 0 <= hora < 6:
            print("Se cambiara en la madrugada (0 a 5 a. m. de Lima).")
            return
    if otra is None or b_otra >= TOPE_DESTINO or (not a.forzar and b_act - b_otra < DIFERENCIA):
        # Ninguna de las existentes conviene: si la activa ya gasto mucho, se crea una base nueva
        if a.forzar or b_act >= NUEVA_DESDE:
            try:
                otra, b_otra = bases_auto.crear("principal"), 0
            except Exception as e:  # noqa: BLE001
                print(f"::error title=Base principal::No se pudo crear una base principal nueva: {str(e)[:400]}")
                raise SystemExit(1)
        else:
            print("Ninguna otra base principal tiene suficiente cupo libre todavia; se sigue con la activa.")
            return

    marcar("copiando", detalle=f"copiando de {principal.nombre(act)} a {principal.nombre(otra)}")
    try:
        # Que terminen las tareas que estan escribiendo (las nuevas ya no arrancan: estado "copiando")
        en_curso = []
        for _ in range(80):
            en_curso = [n for n in tareas_en_curso() if n not in ("Cupos de Neon", "Cambiar base principal")]
            if not en_curso:
                break
            print(f"  esperando a que terminen: {', '.join(sorted(set(en_curso)))}")
            time.sleep(60)
        if en_curso:
            marcar("ok", detalle="cambio postergado: habia tareas en curso; se intenta en la hora siguiente")
            print("Hay tareas que siguen en curso; se intentara en la hora siguiente.")
            return
        inicio = time.time()
        origen, destino = principal.url_de(act), principal.url_de(otra)
        with tempfile.TemporaryDirectory() as TMP:
            os.chmod(TMP, 0o777)
            copiar(origen, destino)
        c1, c2 = conteos(origen), conteos(destino)
        distintos = {k: (v, c2.get(k)) for k, v in c1.items() if c2.get(k) != v}
        if distintos:
            raise RuntimeError(f"la copia no coincide: {distintos}")
        detalle = (f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: copiada de {principal.nombre(act)} "
                   f"({b_act / GB:.2f} GB transferidos) a {principal.nombre(otra)} en {time.time() - inicio:.0f} s; "
                   f"{c1.get('normas', 0)} normas, {c1.get('proyectos_ley', 0)} proyectos, {c1.get('analisis', 0)} analisis")
        marcar("ok", activa=otra, detalle=detalle)
        print(f"::notice title=Base principal::Ahora se usa la {principal.nombre(otra)}. {detalle}")
    except Exception as e:  # noqa: BLE001
        marcar("ok", detalle=f"fallo la copia: {str(e)[:500]}")
        print(f"::error title=Base principal::No se pudo cambiar; se sigue usando la {principal.nombre(act)}. {str(e)[:900]}")
        raise SystemExit(1)


TMP = ""

if __name__ == "__main__":
    main()
