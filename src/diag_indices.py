import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
for a, b in (("agua no s une", "agua nos une"), ("elgobier no", "elgobierno")):
    cur.execute("UPDATE normas SET tipo = replace(tipo, %s, %s) WHERE numero = '' AND tipo LIKE %s", (a, b, f"%{a}%")); print(a, cur.rowcount)
cur.execute("SELECT tipo FROM normas WHERE tipo ILIKE '%nitoge%'"); print(cur.fetchall())
c.commit()
