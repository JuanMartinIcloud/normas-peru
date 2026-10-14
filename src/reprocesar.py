"""Borra las normas marcadas por error como "sin PDF" (enlaces antiguos de El Peruano no reconocidos)
y reinicia el avance de los trabajadores de normas, para que se vuelvan a descargar."""
import os
import psycopg2

for i in (1, 2, 3, 5, 6, 7, 8, 9):
    url = os.getenv(f"TEXTOS_URL_{i}", "").strip()
    if not url:
        continue
    try:
        c = psycopg2.connect(url, connect_timeout=60); c.autocommit = True; cur = c.cursor()
        cur.execute("DELETE FROM documentos WHERE tipo = 'N' AND estado = 'sin_pdf'")
        print(f"texto {i}: {cur.rowcount} marcas 'sin PDF' borradas")
        cur.execute("SELECT to_regclass('avance')")
        if cur.fetchone()[0]:
            cur.execute("DELETE FROM avance WHERE trabajador LIKE 'normas-%%'")
            print(f"texto {i}: {cur.rowcount} avances de normas reiniciados")
        c.close()
    except Exception as e:
        print(f"::warning title=texto {i}::{str(e)[:300]}")
