import { neon } from "@neondatabase/serverless";
import { unstable_noStore as sinCache } from "next/cache";

// Busqueda en el TEXTO COMPLETO de normas y proyectos (tabla "textos").
// Base 0 = la principal (DATABASE_URL); 1, 2... = las adicionales de TEXTOS_URLS (separadas por coma).

const MAX_IDS = 50000;

function bases() {
  const extra = (process.env.TEXTOS_URLS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return [process.env.DATABASE_URL, ...extra];
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
    bases().map((url) =>
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
