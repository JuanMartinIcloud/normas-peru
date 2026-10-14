import { neon } from "@neondatabase/serverless";
import { unstable_noStore as sinCache } from "next/cache";

// Busqueda en el TEXTO COMPLETO de normas y proyectos.
// El texto esta en las bases de texto (variables TEXTOS_URL_1 a TEXTOS_URL_9), tabla "documentos".
// Cada documento se identifica con una clave estable:
//   normas    -> hash_unico
//   proyectos -> "periodo|camara|numero"

const MAX_CLAVES = 5000;   // por base y por busqueda

export function claveProyecto(p) {
  return `${p.periodo}|${p.camara}|${p.numero}`;
}

function bases() {
  const lista = [];
  for (let i = 1; i <= 9; i++) {
    if (i === 4) continue; // TEXTOS_URL_4 se usa por ahora como base principal (ver lib/db.js)
    const url = (process.env[`TEXTOS_URL_${i}`] || "").trim();
    if (url) lista.push({ numero: i, url });
  }
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
  return /relation .*documentos.* does not exist|42P01/i.test(`${e && e.code} ${e && e.message}`);
}

// Ejecuta la consulta en todas las bases de texto; si una no tiene la tabla aun, la omite
async function enTodas(sql, params) {
  const respuestas = await Promise.all(
    bases().map((b) =>
      enBase(b.url, sql, params).catch((e) => {
        if (tablaFaltante(e)) return [];
        throw e;
      })
    )
  );
  return respuestas.flat();
}

// Claves de los documentos cuyo texto completo contiene lo buscado
export async function clavesPorTexto(tipo, terminos) {
  const lista = (terminos || []).filter(Boolean);
  if (!lista.length || !bases().length) return [];
  const filas = await enTodas(
    `SELECT clave FROM documentos
     WHERE tipo = $1 AND to_tsvector('spanish', texto) @@ (${consultaTs(lista, 2)})
     LIMIT ${MAX_CLAVES}`,
    [tipo, ...lista]
  );
  return filas.map((r) => r.clave);
}

// Pasajes del texto donde aparece lo buscado: { clave: "…texto con [[palabra]]…" }
export async function fragmentos(tipo, claves, terminos) {
  const lista = (terminos || []).filter(Boolean);
  const salida = {};
  const ks = (claves || []).filter(Boolean);
  if (!lista.length || !ks.length || !bases().length) return salida;
  const filas = await enTodas(
    `SELECT clave,
            ts_headline('spanish', left(texto, 80000), (${consultaTs(lista, 3)}),
              'MaxFragments=2, MaxWords=35, MinWords=15, ShortWord=3, StartSel=[[, StopSel=]], FragmentDelimiter=" … "') AS frag
     FROM documentos WHERE tipo = $1 AND clave = ANY($2::text[]) AND texto <> ''`,
    [tipo, ks, ...lista]
  );
  for (const r of filas) if (r.frag && /\[\[/.test(r.frag)) salida[r.clave] = r.frag;
  return salida;
}

// Texto completo guardado de un documento (o "" si no esta o es escaneado sin texto)
export async function textoCompleto(tipo, clave) {
  if (!clave || !bases().length) return "";
  const filas = await enTodas(`SELECT estado, texto FROM documentos WHERE tipo = $1 AND clave = $2`, [tipo, clave]);
  const ok = filas.find((f) => f.estado === "ok" && f.texto);
  return ok ? ok.texto : "";
}

// Estado de cada base de texto y del avance (para /api/estado)
export async function estadoBases() {
  const salida = { bases: [], avance: [] };
  for (const b of bases()) {
    try {
      const [t] = await enBase(b.url, `SELECT pg_size_pretty(pg_database_size(current_database())) AS tamano`, []);
      let documentos = {};
      try {
        const filas = await enBase(b.url, `SELECT tipo || '_' || estado AS k, count(*)::int AS n FROM documentos GROUP BY 1`, []);
        for (const f of filas) documentos[f.k] = f.n;
      } catch (e) {
        if (!tablaFaltante(e)) throw e;
        documentos = "tabla aun no creada";
      }
      salida.bases.push({ base: b.numero, tamano: t.tamano, documentos });
      // El avance de la indexacion esta en la base de texto 2 (la 1 se lleno)
      if (b.numero === 2) {
        try {
          salida.avance = await enBase(
            b.url,
            `SELECT trabajador, cursor::text AS hasta, terminado, procesados, actualizado::text AS actualizado
             FROM avance ORDER BY trabajador`,
            []
          );
        } catch (e) {
          salida.avance = [];
        }
      }
    } catch (e) {
      salida.bases.push({ base: b.numero, error: String(e.message || e) });
    }
  }
  return salida;
}
