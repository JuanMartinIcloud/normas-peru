"""Diagnostico temporal: proyectos similares con el nuevo calculo."""
import os, psycopg2
c = psycopg2.connect(os.environ["DATABASE_URL"]); cur = c.cursor()
SQL = """WITH b AS (
       SELECT ARRAY(SELECT unnest(tsvector_to_array(to_tsvector('spanish', %(t)s)))
                    EXCEPT SELECT unnest(tsvector_to_array(to_tsvector('spanish', %(g)s)))) AS lx
     ),
     c AS (
       SELECT p.id, p.numero, p.periodo, p.camara, p.num_pley, p.url, p.fecha_presentacion, p.titulo, p.proponente, p.estado,
              (SELECT count(*) FROM unnest(tsvector_to_array(to_tsvector('spanish', coalesce(p.titulo,'')))) w
                WHERE w = ANY(b.lx)) AS comunes,
              cardinality(b.lx) AS total
       FROM proyectos_ley p, b
       WHERE p.id <> %(i)s AND cardinality(b.lx) > 0
         AND to_tsvector('spanish', coalesce(p.titulo,'')) @@ array_to_string(ARRAY(SELECT quote_literal(x) FROM unnest(b.lx) x), ' | ')::tsquery
     )
     SELECT id::text AS id, numero, periodo, camara, num_pley, url, fecha_presentacion::text AS fecha,
            titulo, proponente, estado, comunes::float / total AS parecido
     FROM c
     WHERE comunes >= LEAST(total, GREATEST(2, CEIL(total * 0.35)))
     ORDER BY comunes DESC, fecha_presentacion DESC NULLS LAST
     LIMIT 25"""
G = """ley leyes proyecto proposicion proposición legislativa legislativo modifica modificar modificación artículo articulo
  artículos decreto decretos establece establecer nacional numeral incorpora incorporar regula regular pública público publica
  fin marco general norma normas sistema perú peru república congreso declara declarar interés necesidad año años texto único
  ordenado supremo disposición complementaria final transitoria actualización conformidad segunda reglamento garantizar
  fortalecer promover mediante dispone aprueba deroga crea crear diversas diversos medidas objeto aplicación caso
  actualizacion cámara diputados senado pl cr cd"""
for num in ("00590-2026-2031-CD", "00586-2026-2031-CD"):
    cur.execute("SELECT id, titulo FROM proyectos_ley WHERE numero = %s LIMIT 1", (num,))
    r = cur.fetchone()
    if not r: print("no", num); continue
    print("BASE", num, r[1][:150])
    cur.execute(SQL, dict(t=r[1], i=r[0], g=G))
    for f in cur.fetchall()[:8]: print("  ", round(f[-1]*100), f[1], (f[7] or "")[:120])
