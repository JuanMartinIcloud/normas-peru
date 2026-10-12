import { neon } from "@neondatabase/serverless";
import { unstable_noStore as sinCache } from "next/cache";

export function consultar(texto, params = []) {
  sinCache(); // cada consulta se hace en el momento, nunca se reutiliza una respuesta guardada
  if (!process.env.DATABASE_URL) {
    throw new Error("Falta la variable DATABASE_URL en Vercel (Settings > Environment Variables).");
  }
  // cache: "no-store" impide que Next.js guarde respuestas viejas de la base:
  // sin esto, la pagina podia mostrar cifras de hace dias en lugar de las actuales.
  const sql = neon(process.env.DATABASE_URL, { fetchOptions: { cache: "no-store" } });
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
  // Busca en la sumilla, numero y entidad, y tambien en el texto completo de la norma
  // (texto_tsv: disponible para las normas cuyo PDF ya se leyo)
  const buscados = [f.q, ...(f.terminos || [])].filter(Boolean);
  if (buscados.length) {
    const partes = [];
    for (const termino of buscados) {
      const a = p(termino);
      partes.push(
        `to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,'')) @@ plainto_tsquery('spanish', ${a})`,
        `texto_tsv @@ plainto_tsquery('spanish', ${a})`
      );
    }
    if (f.q && /\d/.test(f.q)) partes.push(`numero ILIKE ${p(`%${f.q}%`)}`);
    cond.push(`(${partes.join(" OR ")})`);
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
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
