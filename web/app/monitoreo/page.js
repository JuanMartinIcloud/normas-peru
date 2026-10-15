import { leerFiltrosMonitoreo, normasAnalizadas, proyectosAnalizados } from "../../lib/monitoreo";
import { leerPeriodo } from "../../lib/periodo";
import { Barras, contar } from "./Graficos";
import BotonEjecutivo from "./BotonEjecutivo";

export const metadata = { title: "Resumen ejecutivo · Monitoreo empresarial" };

const CALS = ["Favorable", "Desfavorable", "Para seguimiento"];

export default async function ResumenEjecutivo({ searchParams }) {
  const sp = searchParams || {};
  const per = leerPeriodo(sp);
  const f = leerFiltrosMonitoreo({});
  let normas = [];
  let proyectos = [];
  let error = "";
  try {
    [normas, proyectos] = await Promise.all([normasAnalizadas(f, per.desde, per.hasta), proyectosAnalizados(f, per.desde, per.hasta)]);
  } catch (e) {
    error = String(e.message || e);
  }
  const todos = [...normas.map((n) => ({ ...n, origen: "N" })), ...proyectos.map((p) => ({ ...p, origen: "P" }))];
  const cuenta = (campo, valor) => todos.filter((x) => x[campo] === valor).length;
  const sectores = contar(todos, "sector");
  const nombre = (x) => (x.origen === "N" ? [x.tipo, x.numero].filter(Boolean).join(" N° ") : `Proposición ${x.numero}`);
  const destacados = todos.filter((x) => x.impacto === "Alto").slice(0, 15);

  return (
    <>
      <h1>Resumen ejecutivo · {per.nombre}</h1>
      <form className="filtros" method="get" action="/monitoreo">
        <label>
          Mes
          <input type="month" name="mes" defaultValue={per.tipo === "mes" ? per.mes : ""} />
        </label>
        <label>
          o un día
          <input type="date" name="fecha" defaultValue={per.fecha} />
        </label>
        <div className="acciones">
          <button className="boton" type="submit">Ver</button>
        </div>
      </form>
      {error && <div className="error"><strong>No se pudo leer el reporte.</strong><p>{error}</p></div>}

      <div className="kpis">
        <div className="kpi"><div className="n">{normas.length}</div><div className="t">Normas legales con impacto</div></div>
        <div className="kpi"><div className="n">{proyectos.length}</div><div className="t">Proyectos de ley con impacto</div></div>
        <div className="kpi"><div className="n" style={{ color: "#2f8f4e" }}>{cuenta("calificacion", "Favorable")}</div><div className="t">Favorables</div></div>
        <div className="kpi"><div className="n" style={{ color: "#c0392b" }}>{cuenta("calificacion", "Desfavorable")}</div><div className="t">Desfavorables</div></div>
        <div className="kpi"><div className="n" style={{ color: "#a07800" }}>{cuenta("calificacion", "Para seguimiento")}</div><div className="t">Para seguimiento</div></div>
        <div className="kpi"><div className="n">{cuenta("impacto", "Alto")}</div><div className="t">De impacto alto</div></div>
      </div>

      <BotonEjecutivo desde={per.desde} hasta={per.hasta} nombre={per.nombre} cantidad={todos.length} />

      <div className="graficos">
        <Barras titulo="Por calificación" datos={contar(todos, "calificacion")} />
        <Barras titulo="Por nivel de impacto" datos={contar(todos, "impacto")} />
        <Barras titulo="Por sector económico" datos={sectores} />
        <Barras titulo="Por comité de AmCham" datos={contar(todos, "comites")} />
      </div>

      <h2 className="seccion">Cuadro del informe: sector económico por calificación</h2>
      <div className="envoltura-tabla">
        <table className="tabla-mon">
          <thead>
            <tr><th>Sector económico</th>{CALS.map((c) => <th key={c} className="num">{c}</th>)}<th className="num">Total</th></tr>
          </thead>
          <tbody>
            {sectores.map((s) => (
              <tr key={s.etiqueta}>
                <td>{s.etiqueta}</td>
                {CALS.map((c) => (
                  <td key={c} className="num">{todos.filter((x) => x.sector === s.etiqueta && x.calificacion === c).length || ""}</td>
                ))}
                <td className="num"><strong>{s.valor}</strong></td>
              </tr>
            ))}
            <tr>
              <td><strong>Total</strong></td>
              {CALS.map((c) => <td key={c} className="num"><strong>{cuenta("calificacion", c)}</strong></td>)}
              <td className="num"><strong>{todos.length}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="seccion">Documentos de impacto alto</h2>
      {destacados.length === 0 ? (
        <p className="vacio">No hay documentos de impacto alto en este periodo.</p>
      ) : (
        <div className="envoltura-tabla">
          <table className="tabla-mon">
            <thead><tr><th>Documento</th><th>Sector</th><th>Calificación</th><th>En qué consiste</th></tr></thead>
            <tbody>
              {destacados.map((x) => (
                <tr key={`${x.origen}-${x.analisis_id}`}>
                  <td>{nombre(x)}</td><td>{x.sector}</td><td>{x.calificacion}</td><td>{x.resumen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="ia-pendiente">
        Más detalle en <a href={`/monitoreo/impacto?${per.tipo === "mes" ? `mes=${per.mes}` : `fecha=${per.fecha}`}`}>Impacto</a>,{" "}
        <a href={`/monitoreo/normas?mes=${per.mes}`}>Normas legales</a> y <a href="/monitoreo/congreso">Congreso</a>.
      </p>
    </>
  );
}
