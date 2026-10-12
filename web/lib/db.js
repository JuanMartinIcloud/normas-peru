import { neon } from "@neondatabase/serverless";

export function consultar(texto, params = []) {
  if (!process.env.DATABASE_URL) {
    throw new Error("Falta la variable DATABASE_URL en Vercel (Settings > Environment Variables).");
  }
  const sql = neon(process.env.DATABASE_URL);
  // Versiones nuevas del paquete usan sql.query(texto, params);
  // las 0.x aceptan sql(texto, params) directamente.
  if (typeof sql.query === "function") return sql.query(texto, params);
  return sql(texto, params);
}

const FECHA = /^\d{4}-\d{2}-\d{2}$/;
const ANIO = /^\d{4}$/;

export const POR_PAGINA = 50;

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
  if (f.q) {
    const a = p(f.q);
    const b = p(`%${f.q}%`);
    cond.push(
      `(to_tsvector('spanish', coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,'')) @@ plainto_tsquery('spanish', ${a}) OR numero ILIKE ${b})`
    );
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
}

export function hoyLima() {
  // Fecha de hoy en Lima (UTC-5), formato AAAA-MM-DD
  const d = new Date(Date.now() - 5 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}
