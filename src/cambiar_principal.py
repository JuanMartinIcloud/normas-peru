"""Cambia la base principal a la otra copia cuando la activa se acerca a su cupo de transferencia.

    python src/cambiar_principal.py            # decide solo (lo corre "Cupos de Neon" cada hora)
    python src/cambiar_principal.py --forzar   # cambia ahora (flujo "Cambiar base principal")

Regla (cupo gratuito de Neon: 5 GB de transferencia al mes por proyecto):
- Si la base activa llega a 3,5 GB en el mes y la otra tiene menos de 1 GB, se copia TODO a la otra y el
  sistema (web y tareas) pasa a usarla. La copia se hace de madrugada (0 a 5 a. m. de Lima), salvo que la
  activa ya pase de 4,3 GB: entonces se hace en ese momento.
- Mientras se copia, las tareas automaticas esperan (estado "copiando"); la web sigue leyendo la base activa.
- La copia gasta de la base activa mas o menos lo que pesan sus datos (unos 0,25 GB); por eso se cambia a
  los 3,5 GB y no al final.
- Antes de cambiar se verifica que las dos bases tengan las mismas filas en cada tabla. Si algo falla,
  el sistema sigue con la base de siempre y nada se pierde.
"""
import argparse
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone

import psycopg2
import requests

import cupos
import principal

CAMBIO_BYTES = int(3.5 * 10 ** 9)
URGENTE_BYTES = int(4.3 * 10 ** 9)
OTRA_MAXIMO = int(1.0 * 10 ** 9)
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


def main():
    global TMP
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    if not principal.control_url():
        raise SystemExit("Falta el secreto TEXTOS_URL_2 (base de control).")
    act, estado = principal.leer(estricto=True)
    otra = 11 if act == 4 else 4
    if not principal.url_de(act) or not principal.url_de(otra):
        raise SystemExit("Faltan los secretos TEXTOS_URL_4 o TEXTOS_URL_11.")
    b_act, b_otra = transferido(act), transferido(otra)
    print(f"Base principal activa: {principal.NOMBRE[act]} con {b_act / 1e9:.2f} GB transferidos este mes; "
          f"la otra, {principal.NOMBRE[otra]}: {b_otra / 1e9:.2f} GB.")
    if estado == "copiando":
        print("Habia una copia sin terminar (la tarea anterior se corto): se vuelve a intentar.")
    elif not a.forzar:
        if b_act < CAMBIO_BYTES:
            print("No hace falta cambiar.")
            return
        if b_otra >= OTRA_MAXIMO:
            print(f"::warning title=Base principal::La activa llego a {b_act / 1e9:.2f} GB pero la otra tambien gasto "
                  f"{b_otra / 1e9:.2f} GB este mes: no se cambia. El freno de 4 GB y la emergencia de 4,6 GB siguen.")
            return
        hora = (datetime.now(timezone.utc) - timedelta(hours=5)).hour
        if b_act < URGENTE_BYTES and not 0 <= hora < 6:
            print("Se cambiara en la madrugada (0 a 5 a. m. de Lima).")
            return

    marcar("copiando", detalle=f"copiando de {principal.NOMBRE[act]} a {principal.NOMBRE[otra]}")
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
        with tempfile.TemporaryDirectory() as TMP:
            os.chmod(TMP, 0o777)
            copiar(principal.url_de(act), principal.url_de(otra))
        c1, c2 = conteos(principal.url_de(act)), conteos(principal.url_de(otra))
        distintos = {k: (v, c2.get(k)) for k, v in c1.items() if c2.get(k) != v}
        if distintos:
            raise RuntimeError(f"la copia no coincide: {distintos}")
        detalle = (f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: copiada de {principal.NOMBRE[act]} "
                   f"({b_act / 1e9:.2f} GB transferidos) en {time.time() - inicio:.0f} s; "
                   f"{c1.get('normas', 0)} normas, {c1.get('proyectos_ley', 0)} proyectos, {c1.get('analisis', 0)} analisis")
        marcar("ok", activa=otra, detalle=detalle)
        print(f"::notice title=Base principal::Ahora se usa la {principal.NOMBRE[otra]}. {detalle}")
    except Exception as e:  # noqa: BLE001
        marcar("ok", detalle=f"fallo la copia: {str(e)[:500]}")
        print(f"::error title=Base principal::No se pudo cambiar; se sigue usando la {principal.NOMBRE[act]}. {str(e)[:900]}")
        raise SystemExit(1)


TMP = ""

if __name__ == "__main__":
    main()
