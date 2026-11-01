"""Limpieza unica (31/10/2026): deshace la rotacion de bases principales agregada ese dia.
- Elimina en Neon la base de prueba normas-auto-13 (creada automaticamente ese dia, vacia).
- Borra de la base de control las tablas "principal" y "bases_extra" (esta ultima guardaba conexiones).
Este archivo y su flujo se borran despues de usarse."""
import os

import psycopg2
import requests

h = {"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"}
c = psycopg2.connect(os.environ["TEXTOS_URL_2"], connect_timeout=60)
c.autocommit = True
cur = c.cursor()
cur.execute("SELECT to_regclass('public.bases_extra') IS NOT NULL")
proyectos = []
if cur.fetchone()[0]:
    cur.execute("SELECT numero, rol, proyecto FROM bases_extra WHERE numero > 12")
    proyectos = cur.fetchall()
for numero, rol, pid in proyectos:
    if not pid:
        continue
    d = requests.get(f"https://console.neon.tech/api/v2/projects/{pid}", headers=h, timeout=60).json().get("project", {})
    if d.get("name") != f"normas-auto-{numero}":
        print(f"::warning::El proyecto {pid} no se llama normas-auto-{numero} ({d.get('name')}); no se borra")
        continue
    r = requests.delete(f"https://console.neon.tech/api/v2/projects/{pid}", headers=h, timeout=120)
    print(f"::notice::Base normas-auto-{numero} ({rol}) eliminada en Neon: HTTP {r.status_code}")
cur.execute("DROP TABLE IF EXISTS bases_extra")
cur.execute("DROP TABLE IF EXISTS principal")
print("::notice::Tablas principal y bases_extra borradas de la base de control")
c.close()
