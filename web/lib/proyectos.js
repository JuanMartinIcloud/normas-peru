// Filtros y busqueda de proyectos de ley (los usa la pagina /proyectos, /buscar y la IA)
import { leerTerminos } from "./db";

const FECHA = /^\d{4}-\d{2}-\d{2}$/;

export function leerFiltrosProyectos(sp = {}) {
  const v = (k) => (typeof sp[k] === "string" ? sp[k].trim() : "");
  return {
    q: v("q").slice(0, 200),
    periodo: /^\d{4}$/.test(v("periodo")) ? v("periodo") : "",
    estado: v("estado").slice(0, 100),
    rubro: v("rubro").slice(0, 100),
    proponente: v("proponente").slice(0, 100),
    desde: FECHA.test(v("desde")) ? v("desde") : "",
    hasta: FECHA.test(v("hasta")) ? v("hasta") : "",
    terminos: leerTerminos(sp.t),
    pagina: Math.max(1, parseInt(v("p"), 10) || 1),
  };
}

// Arma el WHERE con parametros ($1, $2...) para evitar inyeccion SQL
export function whereProyectos(f) {
  const cond = [];
  const params = [];
  const p = (x) => {
    params.push(x);
    return `$${params.length}`;
  };
  if (f.periodo) cond.push(`periodo = ${p(f.periodo)}`);
  if (f.estado) cond.push(`estado = ${p(f.estado)}`);
  if (f.rubro) cond.push(`rubro = ${p(f.rubro)}`);
  if (f.proponente) cond.push(`proponente = ${p(f.proponente)}`);
  if (f.desde) cond.push(`fecha_presentacion >= ${p(f.desde)}`);
  if (f.hasta) cond.push(`fecha_presentacion <= ${p(f.hasta)}`);
  // Busca en el titulo y en la sumilla extensa del expediente (por palabras: reconoce plurales y
  // variantes; admite "frase exacta"), por texto en titulo, autores o numero, y en el texto completo
  const buscados = [f.q, ...(f.terminos || [])].filter(Boolean);
  if (buscados.length) {
    const partes = buscados.map(
      (t) => `to_tsvector('spanish', coalesce(titulo,'') || ' ' || coalesce(sumilla,'')) @@ websearch_to_tsquery('spanish', ${p(t)})`
    );
    if (f.q) {
      const like = p(`%${f.q.replace(/"/g, "")}%`);
      partes.push(`titulo ILIKE ${like}`, `autor ILIKE ${like}`, `numero ILIKE ${like}`);
    }
    // Ids hallados en el texto completo del PDF del proyecto (ver prepararBusqueda)
    if (f.idsTexto && f.idsTexto.length) partes.push(`id = ANY(${p(f.idsTexto)}::bigint[])`);
    cond.push(`(${partes.join(" OR ")})`);
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
}
