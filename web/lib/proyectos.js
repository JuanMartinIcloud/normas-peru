// Filtros y busqueda de proyectos de ley (los usa la pagina /proyectos, /buscar y la IA)

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
  if (f.q) {
    // Por palabras (encuentra "violencia juvenil" aunque esten separadas o en plural) o por frase exacta
    const palabras = p(f.q);
    const like = p(`%${f.q}%`);
    cond.push(
      `(to_tsvector('spanish', coalesce(titulo,'')) @@ plainto_tsquery('spanish', ${palabras})
        OR titulo ILIKE ${like} OR autor ILIKE ${like} OR numero ILIKE ${like})`
    );
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
}
