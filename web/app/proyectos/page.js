import { consultar, POR_PAGINA } from "../../lib/db";

export const dynamic = "force-dynamic";

const FECHA = /^\d{4}-\d{2}-\d{2}$/;

function leer(sp = {}) {
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

function armarWhere(f) {
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
    const like = p(`%${f.q}%`);
    cond.push(`(titulo ILIKE ${like} OR autor ILIKE ${like} OR numero ILIKE ${like})`);
  }
  return { where: cond.length ? `WHERE ${cond.join(" AND ")}` : "", params };
}

function enlace(f, cambios = {}) {
  const base = { ...f, ...cambios };
  const qs = new URLSearchParams();
  for (const k of ["q", "periodo", "estado", "rubro", "proponente", "desde", "hasta"]) {
    if (base[k]) qs.set(k, base[k]);
  }
  if (base.pagina > 1) qs.set("p", String(base.pagina));
  const s = qs.toString();
  return s ? `/proyectos?${s}` : "/proyectos";
}

async function cargar(f) {
  const { where, params } = armarWhere(f);
  const offset = (f.pagina - 1) * POR_PAGINA;
  const [resumen, periodos, estados, rubros, proponentes, filas, total] = await Promise.all([
    consultar(`SELECT count(*)::int AS total, min(fecha_presentacion)::text AS primera, max(fecha_presentacion)::text AS ultima FROM proyectos_ley`),
    consultar(`SELECT periodo AS valor, count(*)::int AS n FROM proyectos_ley GROUP BY 1 ORDER BY 1 DESC`),
    consultar(`SELECT estado AS valor, count(*)::int AS n FROM proyectos_ley WHERE estado IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT rubro AS valor, count(*)::int AS n FROM proyectos_ley WHERE rubro IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT proponente AS valor, count(*)::int AS n FROM proyectos_ley WHERE proponente IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 30`),
    consultar(
      `SELECT id, periodo, camara, numero, fecha_presentacion::text AS fecha, titulo, autor, proponente, estado, rubro
       FROM proyectos_ley ${where} ORDER BY fecha_presentacion DESC NULLS LAST, id DESC LIMIT ${POR_PAGINA} OFFSET ${offset}`,
      params
    ),
    consultar(`SELECT count(*)::int AS n FROM proyectos_ley ${where}`, params),
  ]);
  return { resumen: resumen[0], periodos, estados, rubros, proponentes, filas, total: total[0].n };
}

function Opciones({ lista }) {
  return (
    <>
      <option value="">Todos</option>
      {lista.map((o) => (
        <option key={o.valor} value={o.valor}>
          {o.valor} ({o.n.toLocaleString("es-PE")})
        </option>
      ))}
    </>
  );
}

export default async function Proyectos({ searchParams }) {
  const f = leer(searchParams || {});
  let datos;
  try {
    datos = await cargar(f);
  } catch (e) {
    return (
      <main className="contenedor">
        <h1>Proyectos de ley</h1>
        <div className="error">
          <strong>No se pudo leer la base de datos.</strong>
          <p>{String(e.message || e)}</p>
          <p>Si dice que la tabla no existe, ejecuta en GitHub el flujo “Crear tablas” y luego “Proyectos de ley (Congreso)”.</p>
        </div>
      </main>
    );
  }

  const { resumen, periodos, estados, rubros, proponentes, filas, total } = datos;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <main className="contenedor">
      <h1>Proyectos de ley</h1>
      <p className="sub">
        {resumen.total.toLocaleString("es-PE")} proyectos guardados
        {resumen.primera ? ` · presentados entre ${resumen.primera} y ${resumen.ultima}` : ""}
      </p>

      <nav className="atajos" aria-label="Secciones">
        <a className="atajo" href="/">Normas legales</a>
        <a className="atajo activo" href="/proyectos">Proyectos de ley</a>
      </nav>

      <form className="filtros" method="get" action="/proyectos">
        <label className="ancho">
          Buscar por palabra, autor o número
          <input type="search" name="q" defaultValue={f.q} placeholder="Ej.: pensiones, Luque, 14864/2025-CR" />
        </label>
        <label>
          Periodo parlamentario
          <select name="periodo" defaultValue={f.periodo}><Opciones lista={periodos} /></select>
        </label>
        <label>
          Estado
          <select name="estado" defaultValue={f.estado}><Opciones lista={estados} /></select>
        </label>
        <label>
          Rubro
          <select name="rubro" defaultValue={f.rubro}><Opciones lista={rubros} /></select>
        </label>
        <label>
          Quién lo propone
          <select name="proponente" defaultValue={f.proponente}><Opciones lista={proponentes} /></select>
        </label>
        <label>
          Presentado desde
          <input type="date" name="desde" defaultValue={f.desde} />
        </label>
        <label>
          Presentado hasta
          <input type="date" name="hasta" defaultValue={f.hasta} />
        </label>
        <div className="acciones">
          <button className="boton" type="submit">Buscar</button>
          <a className="boton sec" href="/proyectos">Limpiar</a>
        </div>
      </form>

      <p className="resumen">
        {total.toLocaleString("es-PE")} resultados · página {f.pagina} de {paginas.toLocaleString("es-PE")}
      </p>

      {filas.length === 0 ? (
        <p className="vacio">No hay proyectos para esta búsqueda.</p>
      ) : (
        <div className="lista">
          {filas.map((n) => (
            <article className="norma" key={n.id}>
              <div className="linea1">
                <span className="titulo">Proyecto {n.numero}</span>
                <span className="entidad">{n.proponente}</span>
                <span className="fecha">{n.fecha}</span>
              </div>
              <p className="sumilla">{n.titulo}</p>
              {n.autor && <p className="entidad">Autores: {n.autor}</p>}
              <div className="etiquetas">
                {n.estado && <span className="etq">{n.estado}</span>}
                {n.rubro && <span className="etq gris">{n.rubro}</span>}
                <span className="etq gris">Periodo {n.periodo}</span>
              </div>
            </article>
          ))}
        </div>
      )}

      {paginas > 1 && (
        <div className="paginas">
          {f.pagina > 1 && <a className="boton sec" href={enlace(f, { pagina: f.pagina - 1 })}>← Anterior</a>}
          <span>{f.pagina} / {paginas.toLocaleString("es-PE")}</span>
          {f.pagina < paginas && <a className="boton sec" href={enlace(f, { pagina: f.pagina + 1 })}>Siguiente →</a>}
        </div>
      )}
    </main>
  );
}
