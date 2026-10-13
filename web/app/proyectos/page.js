import { consultar, POR_PAGINA, prepararBusqueda } from "../../lib/db";
import { fragmentos } from "../../lib/textos";
import Fragmento from "../Fragmento";
import { urlProyecto } from "../../lib/resumenes";
import { leerFiltrosProyectos, whereProyectos } from "../../lib/proyectos";
import BotonResumir from "../BotonResumir";
import Marcar from "../Marcar";

export const dynamic = "force-dynamic";

function enlace(f, cambios = {}) {
  const base = { ...f, ...cambios };
  const qs = new URLSearchParams();
  for (const k of ["q", "periodo", "estado", "rubro", "proponente", "desde", "hasta"]) {
    if (base[k]) qs.set(k, base[k]);
  }
  if (base.terminos && base.terminos.length) qs.set("t", base.terminos.join("|"));
  if (base.pagina > 1) qs.set("p", String(base.pagina));
  const s = qs.toString();
  return s ? `/proyectos?${s}` : "/proyectos";
}

async function cargar(f) {
  await prepararBusqueda(f, "P");
  const { where, params } = whereProyectos(f);
  const offset = (f.pagina - 1) * POR_PAGINA;
  const [resumen, periodos, estados, rubros, proponentes, filas, total] = await Promise.all([
    consultar(`SELECT count(*)::int AS total, min(fecha_presentacion)::text AS primera, max(fecha_presentacion)::text AS ultima FROM proyectos_ley`),
    consultar(`SELECT periodo AS valor, count(*)::int AS n FROM proyectos_ley GROUP BY 1 ORDER BY 1 DESC`),
    consultar(`SELECT estado AS valor, count(*)::int AS n FROM proyectos_ley WHERE estado IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT rubro AS valor, count(*)::int AS n FROM proyectos_ley WHERE rubro IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT proponente AS valor, count(*)::int AS n FROM proyectos_ley WHERE proponente IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 30`),
    consultar(
      `SELECT id, periodo, camara, numero, num_pley, url, fecha_presentacion::text AS fecha, titulo, sumilla, autor, proponente, estado, rubro, texto_base
       FROM proyectos_ley ${where} ORDER BY fecha_presentacion DESC NULLS LAST, id DESC LIMIT ${POR_PAGINA} OFFSET ${offset}`,
      params
    ),
    consultar(`SELECT count(*)::int AS n FROM proyectos_ley ${where}`, params),
  ]);
  let frags = {};
  try {
    frags = await fragmentos("P", filas, [f.q, ...f.terminos]);
  } catch (e) {
    frags = {};
  }
  return { resumen: resumen[0], periodos, estados, rubros, proponentes, filas, total: total[0].n, frags };
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
  const f = leerFiltrosProyectos(searchParams || {});
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

  const { resumen, periodos, estados, rubros, proponentes, filas, total, frags } = datos;
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
        <a className="atajo" href="/resumenes">Resúmenes diarios</a>
        <a className="atajo" href="/buscar">Buscar en todo</a>
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
        {total.toLocaleString("es-PE")} {total === 1 ? "resultado" : "resultados"} · página {f.pagina} de {paginas.toLocaleString("es-PE")}
      </p>

      {(f.q || f.periodo || f.estado || f.rubro || f.proponente || f.desde || f.hasta || f.terminos.length > 0) && (
        <BotonResumir
          ambito="proyectos"
          cantidad={total}
          filtros={{
            q: f.q, periodo: f.periodo, estado: f.estado, rubro: f.rubro,
            proponente: f.proponente, desde: f.desde, hasta: f.hasta, t: f.terminos.join("|"),
          }}
        />
      )}

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
              {n.sumilla && <p className="entidad">{n.sumilla}</p>}
              <Fragmento texto={frags[String(n.id)]} />
              {n.autor && <p className="entidad">Autores: {n.autor}</p>}
              <div className="etiquetas">
                <Marcar tipo="P" id={String(n.id)} etiqueta={`Proyecto ${n.numero}`} />
                {n.estado && <span className="etq">{n.estado}</span>}
                {n.rubro && <span className="etq gris">{n.rubro}</span>}
                <span className="etq gris">Periodo {n.periodo}</span>
                <span className="enlaces">
                  <a href={`/proyectos/similares?id=${n.id}`}>Similares</a>
                  {urlProyecto(n) && (
                    <>
                      {" · "}
                      <a href={urlProyecto(n)} target="_blank" rel="noopener noreferrer">Ver expediente</a>
                    </>
                  )}
                </span>
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
