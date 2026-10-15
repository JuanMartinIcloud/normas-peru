"""Diagnostico temporal: el indexador y el buscador funcionan sin la base 1."""
import os, sys; sys.path.insert(0, "src")
print("TEXTOS_URL_1 presente:", bool(os.getenv("TEXTOS_URL_1")))
import indexar, psycopg2
b = indexar.Bases()
print("bases de texto en uso:", len(b.urls))
c = psycopg2.connect(os.environ["TEXTOS_URL_12"]); cur = c.cursor()
cur.execute("SELECT clave FROM documentos WHERE tipo='N' ORDER BY random() LIMIT 50"); claves = [r[0] for r in cur.fetchall()]
cur.execute("SELECT clave FROM documentos WHERE tipo='P' ORDER BY random() LIMIT 50"); clp = [r[0] for r in cur.fetchall()]
print("normas de la antigua base 1 encontradas:", len(b.existentes("N", claves)), "de", len(claves))
print("proyectos de la antigua base 1 encontrados:", len(b.existentes("P", clp)), "de", len(clp))
import monitoreo
t = monitoreo.textos("N", claves[:10]); print("textos leidos por el monitoreo:", len(t), "de 10 (algunos pueden no tener texto)")
