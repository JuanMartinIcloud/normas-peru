import { neon } from "@neondatabase/serverless";
import { unstable_noStore as sinCache } from "next/cache";
import { clavesPorTexto, clavesPorGrupos } from "./textos";

// Base principal. La original (DATABASE_URL) agoto su cuota gratuita del mes; mientras tanto se usa
// la base de la variable TEXTOS_URL_4. Para volver a la original basta quitar "TEXTOS_URL_4 ||".
const URL_PRINCIPAL = (process.env.TEXTOS_URL_4 || process.env.DATABASE_URL || "").trim();

export function consultar(texto, params = []) {
  sinCache(); // cada consulta se hace en el momento, nunca se reutiliza una respuesta guardada
  if (!URL_PRINCIPAL) {
    throw new Error("Falta la variable DATABASE_URL en Vercel (Settings > Environment Variables).");
  }
  // cache: "no-store" impide que Next.js guarde respuestas viejas de la base:
  // sin esto, la pagina podia mostrar cifras de hace dias en lugar de las actuales.
  const sql = neon(URL_PRINCIPAL, { fetchOptions: { cache: "no-store" } });
  // Versiones nuevas del paquete usan sql.query(texto, params);
  // las 0.x aceptan sql(texto, params) directamente.
  if (typeof sql.query === "function") return sql.query(texto, params);
  return sql(texto, params);
}

const FECHA = /^\d{4}-\d{2}-\d{2}$/;
const ANIO = /^\d{4}$/;

export const POR_PAGINA = 50;

// Terminos adicionales de busqueda (los que sugiere la IA), separados por "|" en el parametro t
export function leerTerminos(valor) {
  const lista = typeof valor === "string" ? valor.split("|") : [];
  const limpios = [];
  for (const t of lista) {
    const x = t.replace(/\s+/g, " ").trim().slice(0, 80);
    if (x && !limpios.some((y) => y.toLowerCase() === x.toLowerCase())) limpios.push(x);
  }
  return limpios.slice(0, 8);
}

// Lee y limpia los filtros que vienen en la direccion de la pagina
export function leerFiltros(sp = {}) {
  const v = (k) => (typeof sp[k] === "string" ? sp[k].trim() : "");
  const pagina = Math.max(1, parseInt(v("p"), 10) || 1);
  return {
    q: v("q").slice(0, 200),
    fecha: FECHA.test(v("fecha")) ? v("fecha") : "",
    desde: FECHA.test(v("desde")) ? v("desde") : "",
    hasta: FECHA.test(v("hasta")) ? v("hasta") : "",
    anio: ANIO.test(v("anio")) ? v("anio") : "",
    sector: v("sector").slice(0, 100),
    rubro: v("rubro").slice(0, 100),
    tipo: v("tipo").slice(0, 100),
    central: v("central") === "1",
    leyes: v("leyes") === "1",
    terminos: leerTerminos(sp.t),
    refinar: leerTerminos(sp.y),
    pregunta: v("pregunta").slice(0, 300),
    orden: v("orden") === "r" ? "r" : "",
    pagina,
  };
}

// Arma el WHERE con parametros ($1, $2...) para evitar inyeccion SQL
export function construirWhere(f) {
  const cond = [];
  const params = [];
  const p = (valor) => {
    params.push(valor);
    return `$${params.length}`;
  };

  if (f.fecha) cond.push(`fecha = ${p(f.fecha)}`);
  if (f.anio) {
    cond.push(`fecha >= ${p(`${f.anio}-01-01`)} AND fecha < ${p(`${Number(f.anio) + 1}-01-01`)}`);
  }
  if (f.desde) cond.push(`fecha >= ${p(f.desde)}`);
  if (f.hasta) cond.push(`fecha <= ${p(f.hasta)}`);
  if (f.sector) cond.push(`sector = ${p(f.sector)}`);
  if (f.rubro) cond.push(`rubro = ${p(f.rubro)}`);
  if (f.tipo) cond.push(`tipo = ${p(f.tipo)}`);
  if (f.central) cond.push(`sector NOT IN ('Gobiernos Locales', 'Gobiernos Regionales')`);
  // Leyes y normas con rango de ley: Ley, Decreto Legislativo, Decreto de Urgencia, Resolución Legislativa
  if (f.leyes) {
    cond.push(`tipo ~* '^(ley|decreto legislativo|decreto de urgencia|resoluci[oóÓ]n legislativa)( |$)'`);
  }
  // Busca en la sumilla, numero y entidad (admite "frase exacta", OR y -palabra) y, ademas,
  // en el texto completo: f.clavesTexto trae las normas halladas alli (ver prepararBusqueda)
  const buscados = [f.q, ...(f.terminos || [])].filter(Boolean);
  let principal = "";
  if (buscados.length) {
    const partes = buscados.map((termino) => `${TSV_NORMAS} @@ websearch_to_tsquery('spanish', ${p(termino)})`);
    if (f.q && /\d/.test(f.q)) partes.push(`numero ILIKE ${p(`%${f.q.replace(/"/g, "")}%`)}`);
    if (f.clavesTexto && f.clavesTexto.length) partes.push(`hash_unico = ANY(${p(f.clavesTexto)}::text[])`);
    principal = `(${partes.join(" OR ")})`;
  }
  // Filtros sucesivos ("buscar dentro de estos resultados"): cada uno debe cumplirse ademas
  const refinar = f.refinar || [];
  if (refinar.length) {
    const ref = refinar.map((r, i) => {
      const alt = [`${TSV_NORMAS} @@ websearch_to_tsquery('spanish', ${p(r)})`];
      if (/\d/.test(r)) alt.push(`numero ILIKE ${p(`%${r.replace(/"/g, "")}%`)}`);
      const ks = (f.clavesRefinar || [])[i];
      if (ks && ks.length) alt.push(`hash_unico = ANY(${p(ks)}::text[])`);
      return `(${alt.join(" OR ")})`;
    });
    let bloque = [principal, ...ref].filter(Boolean).join(" AND ");
    // documentos cuyo texto completo cumple todo a la vez
    if (f.clavesTodas && f.clavesTodas.length) bloque = `(${bloque}) OR hash_unico = ANY(${p(f.clavesTodas)}::text[])`;
    cond.push(`(${bloque})`);
  } else if (principal) {
    cond.push(principal);
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
}

// Expresion de busqueda sobre sumilla, numero y entidad (igual a la del indice de la base)
export const TSV_NORMAS =
  "to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,''))";

// Orden de los resultados: por relevancia (busqueda con IA) o por fecha.
// Recibe los params del WHERE y les agrega los suyos.
export function ordenNormas(f, params) {
  const buscados = [f.q, ...(f.terminos || []), ...(f.refinar || [])].filter(Boolean);
  if (f.orden !== "r" || !buscados.length) return "fecha DESC, id DESC";
  const q = buscados
    .map((t) => {
      params.push(t);
      return `websearch_to_tsquery('spanish', $${params.length})`;
    })
    .join(" || ");
  return `ts_rank(${TSV_NORMAS}, (${q})) DESC, fecha DESC, id DESC`;
}

export function hoyLima() {
  // Fecha de hoy en Lima (UTC-5), formato AAAA-MM-DD
  const d = new Date(Date.now() - 5 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}

// true si las palabras buscadas no aparecen en la sumilla (o sea, la norma salio por su texto completo
// o por un termino sugerido). Solo sirve para mostrar una etiqueta orientativa.
export function coincideFueraDeSumilla(texto, q) {
  if (!q) return false;
  const base = (s) =>
    String(s || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  const t = base(texto);
  const palabras = base(q).split(/[^a-z0-9ñ]+/).filter((w) => w.length > 3);
  if (!palabras.length) return false;
  return !palabras.every((w) => t.includes(w.slice(0, Math.max(4, w.length - 2))));
}

// Antes de armar el WHERE: busca lo pedido en el texto completo y guarda los ids hallados
export async function prepararBusqueda(f, tipo) {
  const buscados = [f.q, ...(f.terminos || [])].filter(Boolean);
  const refinar = f.refinar || [];
  if (!buscados.length && !refinar.length) return f;
  try {
    const [principal, porFiltro, todas] = await Promise.all([
      buscados.length ? clavesPorTexto(tipo, buscados) : [],
      Promise.all(refinar.map((r) => clavesPorTexto(tipo, [r]))),
      refinar.length ? clavesPorGrupos(tipo, [buscados, ...refinar.map((r) => [r])]) : [],
    ]);
    f.clavesTexto = principal;
    f.clavesRefinar = porFiltro;
    f.clavesTodas = todas;
    if (principal.parcial || todas.parcial || porFiltro.some((x) => x.parcial)) f.avisoTexto = "parcial";
  } catch (e) {
    // Si la busqueda en el texto completo falla, se sigue con la de sumillas y se avisa
    f.clavesTexto = [];
    f.clavesRefinar = [];
    f.clavesTodas = [];
    f.avisoTexto = String(e.message || e);
  }
  return f;
}

// Corrector de errores de escritura (por ejemplo "piscologica" -> "psicológica").
// Usa la tabla "vocabulario" (palabras reales de sumillas y titulos). Devuelve la consulta corregida,
// o "" si no hay nada que corregir. Solo se usa cuando una busqueda no dio resultados.
const quitarTildes = (s) =>
  s.toLowerCase().normalize("NFD").replace(/[̀-̂̄-ͯ]/g, "").normalize("NFC"); // conserva la ñ

export async function corregirConsulta(q) {
  if (!q) return "";
  const partes = q.split(/(\s+)/);
  const palabras = [];
  partes.forEach((p, i) => {
    const limpia = p.replace(/^[-"(]+|[")]+$/g, "");
    if (/^\p{L}{4,}$/u.test(limpia) && !/^(or|and)$/i.test(limpia)) palabras.push({ i, limpia });
  });
  if (!palabras.length) return "";
  let filas;
  try {
    filas = await consultar(
      `SELECT t.w,
              EXISTS (SELECT 1 FROM vocabulario v WHERE v.sin_tilde = t.w) AS existe,
              (SELECT v.palabra FROM vocabulario v
                WHERE v.sin_tilde % t.w AND similarity(v.sin_tilde, t.w) >= 0.4
                ORDER BY similarity(v.sin_tilde, t.w) DESC, v.n DESC LIMIT 1) AS cercana
       FROM unnest($1::text[]) AS t(w)`,
      [palabras.map((p) => quitarTildes(p.limpia))]
    );
  } catch (e) {
    return ""; // sin vocabulario no se corrige, la busqueda sigue igual
  }
  let cambio = false;
  const salida = [...partes];
  const porPalabra = new Map(filas.map((f) => [f.w, f]));
  palabras.forEach((p) => {
    const f = porPalabra.get(quitarTildes(p.limpia));
    if (f && !f.existe && f.cercana && quitarTildes(f.cercana) !== quitarTildes(p.limpia)) {
      salida[p.i] = partes[p.i].replace(p.limpia, f.cercana);
      cambio = true;
    }
  });
  return cambio ? salida.join("") : "";
}
