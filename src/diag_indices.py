"""Ultimos ajustes de titulos sin numero: palabras que el diccionario no reconocio (plurales)."""
import os, re, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
cambios = [(r"america no s\b", "americanos"), (r"americano s\b", "americanos"), (r"iberoamerica no\b", "iberoamericano"),
           (r"mexicano s\b", "mexicanos"), (r"mejica no s\b", "mejicanos"), (r"gobbier no\b", "gobierno")]
cur.execute(r"SELECT id, tipo FROM normas WHERE numero = '' AND tipo ~* '( no |no s\b| no$)'")
for nid, tipo in cur.fetchall():
    nuevo = tipo
    for a, b in cambios:
        nuevo = re.sub(a, b, nuevo, flags=re.I)
    if nuevo != tipo:
        cur.execute("UPDATE normas SET tipo = %s WHERE id = %s", (nuevo, nid))
        print("corregido:", tipo[:90], "->", nuevo[:90])
    else:
        print("queda:", tipo[:110])
c.commit()
