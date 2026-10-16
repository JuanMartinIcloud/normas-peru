"""Diagnostico temporal: valores de las listas desplegables (para el manual)."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
Q = {
 "normas.rubro": "SELECT rubro, count(*) FROM normas WHERE rubro IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
 "normas.sector": "SELECT sector, count(*) FROM normas WHERE sector IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
 "normas.tipo": "SELECT tipo, count(*) FROM normas WHERE tipo IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 40",
 "proy.periodo": "SELECT periodo, count(*) FROM proyectos_ley GROUP BY 1 ORDER BY 1 DESC",
 "proy.estado": "SELECT estado, count(*) FROM proyectos_ley WHERE estado IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
 "proy.rubro": "SELECT rubro, count(*) FROM proyectos_ley WHERE rubro IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
 "proy.proponente": "SELECT proponente, count(*) FROM proyectos_ley WHERE proponente IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 30",
}
for k, q in Q.items():
    cur.execute(q); print("##", k); print(" | ".join(f"{a} ({b})" for a, b in cur.fetchall()))
