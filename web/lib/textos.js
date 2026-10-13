import { neon } from "@neondatabase/serverless";
import { unstable_noStore as sinCache } from "next/cache";

// Busqueda en el TEXTO COMPLETO de normas y proyectos (tabla "textos").
// Base 0 = la principal (DATABASE_URL); base i = la de la variable TEXTOS_URL_i (i = 1 a 9).

const MAX_IDS = 50000;

// Lista con posicion fija: bases()[i] es la base i (null si esa variable no existe)
function bases() {
  const lista = [process.env.DATABASE_URL];
  for (let i = 1; i <= 9; i++) lista.push((process.env[`TEXTOS_URL_${i}`] || "").trim() || null);
  return lista;
}

function enBase(url, texto, params) {
  sinCache();
  const sql = neon(url, { fetchOptions: { cache: "no-store" } });
  if (typeof sql.query === "function") return sql.query(texto, params);
  return sql(texto, params);
}

// Consulta de busqueda: admite "frase exacta" entre comillas, OR y -palabra (como Google).
// Varios terminos se combinan con O: basta que el documento contenga uno.
function consultaTs(terminos, primerParametro) {
  return terminos.map((_, i) => `websearch_to_tsquery('spanish', $${primerParametro + i})`).join(" || ");
}

function tablaFaltante(e) {
  return /relation .*textos.* does not exist|42P01/i.test(`${e && e.code} ${e && e.message}`);
}

// ids (como texto) de los documentos cuyo texto completo contiene lo buscado
export async function idsPorTexto(tipo, terminos) {
  const lista = (terminos || []).filter(Boolean);
  if (!lista.length) return [];
  const sql = `SELECT doc_id::text AS id FROM textos
               WHERE tipo = $1 AND to_tsvector('spanish', texto) @@ (${consultaTs(lista, 2)})
               LIMIT ${MAX_IDS}`;
  const respuestas = await Promise.all(
    bases().filter(Boolean).map((url) =>
      enBase(url, sql, [tipo, ...lista]).catch((e) => {
        if (tablaFaltante(e)) return [];
        throw e;
      })
    )
  );
  return respuestas.flat().map((r) => r.id);
}

// Fragmentos del texto donde aparece lo buscado: { id: "…texto con [[palabra]]…" }
export async function fragmentos(tipo, filas, terminos) {
  const lista = (terminos || []).filter(Boolean);
  const salida = {};
  if (!lista.length || !filas.length) return salida;
  const porBase = {};
  for (const f of filas) {
    if (f.texto_base === null || f.texto_base === undefined) continue;
    (porBase[f.texto_base] = porBase[f.texto_base] || []).push(String(f.id));
  }
  const urls = bases();
  const sql = `SELECT doc_id::text AS id,
                      ts_headline('spanish', left(texto, 80000), (${consultaTs(lista, 3)}),
                        'MaxFragments=2, MaxWords=35, MinWords=15, ShortWord=3, StartSel=[[, StopSel=]], FragmentDelimiter=" … "') AS frag
               FROM textos WHERE tipo = $1 AND doc_id = ANY($2::bigint[])`;
  await Promise.all(
    Object.entries(porBase).map(async ([base, ids]) => {
      const url = urls[Number(base)];
      if (!url) return;
      try {
        const filasFrag = await enBase(url, sql, [tipo, ids, ...lista]);
        for (const r of filasFrag) if (r.frag && /\[\[/.test(r.frag)) salida[r.id] = r.frag;
      } catch (e) {
        if (!tablaFaltante(e)) throw e;
      }
    })
  );
  return salida;
}

// Texto completo guardado de un documento (o "" si no esta)
export async function textoCompleto(tipo, id, base) {
  const url = bases()[Number(base)];
  if (!url || base === null || base === undefined) return "";
  const filas = await enBase(url, `SELECT texto FROM textos WHERE tipo = $1 AND doc_id = $2`, [tipo, String(id)]);
  return filas[0] ? filas[0].texto : "";
}

// Estado de cada base de texto: tamano y documentos guardados (para /api/estado)
export async function estadoBases() {
  const salida = [];
  const lista = bases();
  for (let i = 0; i < lista.length; i++) {
    if (!lista[i]) continue;
    try {
      const [t] = await enBase(lista[i], `SELECT pg_size_pretty(pg_database_size(current_database())) AS tamano`, []);
      let documentos = 0;
      try {
        const [c] = await enBase(lista[i], `SELECT count(*)::int AS n FROM textos`, []);
        documentos = c.n;
      } catch (e) {
        if (!tablaFaltante(e)) throw e;
        documentos = "tabla aun no creada";
      }
      salida.push({ base: i, tamano: t.tamano, documentos });
    } catch (e) {
      salida.push({ base: i, error: String(e.message || e) });
    }
  }
  return salida;
}
