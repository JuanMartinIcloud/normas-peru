import { leerFiltrosMonitoreo, reporteCongreso, opcionesFiltros, ayerLima, fechaLarga } from "../../../lib/monitoreo";
import { urlProyecto } from "../../../lib/resumenes";
import Filtros from "../Filtros";
import Tarjeta from "../Tarjeta";

export const metadata = { title: "Congreso · Monitoreo empresarial" };

const CAMARA = { D: "Cámara de Diputados", S: "Senado", C: "Congreso" };

function Seccion({ titulo, datos, vacio, mostrarMovimiento }) {
  const { items, cuenta } = datos;
  return (
    <>
      <h3 className="seccion">{titulo}</h3>
      <p className="ia-pendiente">
        {cuenta.total} en total · {cuenta.relevantes} con impacto empresarial
        {cuenta.pendientes > 0 && ` · ${cuenta.pendientes} aún en análisis`}
      </p>
      {items.length === 0 ? (
        <p className="vacio">{cuenta.total ? "Ninguno con impacto empresarial (o todos fueron quitados)." : vacio}</p>
      ) : (
        <div className="lista">
          {items.map((p) => (
            <Tarjeta
              key={`${p.analisis_id}-${p.mov_fecha}`}
              a={p}
              titulo={`Proposición ${p.numero}`}
              subtitulo={`${CAMARA[p.camara] || ""} · ${p.proponente || ""}`}
              fecha={p.mov_fecha || p.fecha_presentacion}
              descripcion={p.titulo}
              movimiento={
                mostrarMovimiento
                  ? [p.mov_comisiones && `Comisión: ${p.mov_comisiones}`, p.mov_detalle].filter(Boolean).join(" · ")
                  : `Estado actual: ${p.estado || "—"}`
              }
              enlaces={[{ texto: "Expediente", url: urlProyecto(p) }]}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default async function CongresoMonitoreo({ searchParams }) {
  const f = leerFiltrosMonitoreo(searchParams || {});
  const fecha = f.fecha || ayerLima();
  f.fecha = fecha;
  let r = null;
  let opciones = { sectores: [] };
  let error = "";
  try {
    [r, opciones] = await Promise.all([reporteCongreso(f, fecha, fecha), opcionesFiltros(fecha, fecha)]);
  } catch (e) {
    error = String(e.message || e);
  }
  const qs = new URLSearchParams({ ...Object.fromEntries(Object.entries(searchParams || {}).filter(([, v]) => typeof v === "string" && v)), fecha }).toString();

  return (
    <>
      <h1>Reporte del Congreso · {fechaLarga(fecha)}</h1>
      <p className="sub">
        Proposiciones legislativas ingresadas, dictámenes de comisiones y autógrafas del día, con su análisis de impacto
        empresarial. El reporte de cada día está listo a las 7:00 a. m. del día siguiente.
      </p>
      <Filtros accion="/monitoreo/congreso" f={f} sectores={opciones.sectores} periodo="dia" />
      {error && <div className="error"><strong>No se pudo leer el reporte.</strong><p>{error}</p></div>}
      {r && (
        <>
          <p className="resumen">
            <a href={`/api/monitoreo/csv?vista=congreso&${qs}`}>Descargar en Excel</a>
          </p>
          <h2 className="seccion">Sección 1 · Cámara de Diputados</h2>
          <Seccion titulo="Proposiciones legislativas ingresadas" datos={r.diputados_ingresadas} vacio="No ingresaron proposiciones este día." />
          <Seccion titulo="Dictámenes emitidos por las comisiones" datos={r.diputados_dictamenes} vacio="No hubo dictámenes este día." mostrarMovimiento />
          <h2 className="seccion">Sección 2 · Cámara de Senadores</h2>
          <Seccion titulo="Proposiciones legislativas ingresadas" datos={r.senado_ingresadas} vacio="No ingresaron proposiciones al Senado este día." mostrarMovimiento />
          <Seccion titulo="Dictámenes emitidos por las comisiones" datos={r.senado_dictamenes} vacio="No hubo dictámenes en el Senado este día." mostrarMovimiento />
          <h2 className="seccion">Sección 3 · Autógrafas de ley</h2>
          <Seccion titulo="Autógrafas" datos={r.autografas} vacio="No hubo autógrafas este día." mostrarMovimiento />
        </>
      )}
    </>
  );
}
