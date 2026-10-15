import { notFound } from "next/navigation";
import { consultar } from "../../../../lib/db";
import { asegurarTablas, FRECUENCIAS, urlBuscador } from "../../../../lib/busquedas";
import AccionesBusqueda from "../AccionesBusqueda";

export const metadata = { title: "Resultados · Búsquedas guardadas" };

export default async function Resultados({ params }) {
  const id = Number(params.id);
  if (!id) notFound();
  await asegurarTablas();
  const [b] = await consultar(`SELECT * FROM busquedas_guardadas WHERE id = $1`, [id]);
  if (!b) notFound();
  const ejecuciones = await consultar(
    `SELECT id, desde::text, hasta::text, total_normas, total_proyectos, normas, proyectos, resumen, enviado, creado_en::text
     FROM busqueda_ejecuciones WHERE busqueda_id = $1 ORDER BY hasta DESC, creado_en DESC LIMIT 60`,
    [id]
  );
  return (
    <>
      <p className="ia-pendiente"><a href="/monitoreo/busquedas">← Búsquedas guardadas</a></p>
      <h1>{b.nombre}</h1>
      <p className="sub">
        {b.pregunta ? `Pregunta: «${b.pregunta}»` : `Palabras: «${b.q}»`} · {FRECUENCIAS[b.frecuencia]} · {b.activa ? "Activa" : "Pausada"}
        {b.terminos?.length > 0 && <><br />Términos: {b.terminos.join(", ")}</>}
        {b.refinar?.length > 0 && <><br />Filtros: {b.refinar.join(", ")}</>}
      </p>
      <div className="etiquetas">
        <a className="boton sec chico" href={urlBuscador(b)}>Abrir en el buscador</a>
        <AccionesBusqueda b={{ id: b.id, nombre: b.nombre, frecuencia: b.frecuencia, activa: b.activa, destinatarios: b.destinatarios || [], con_resumen: b.con_resumen }} />
      </div>
      <h2 className="seccion">Resultados ({ejecuciones.length})</h2>
      {ejecuciones.length === 0 && <p className="vacio">Aún no se ha ejecutado. Pulsa «Ejecutar ahora» o espera a su próxima ejecución.</p>}
      {ejecuciones.map((e, i) => (
        <details key={e.id} className="grafico otros" open={i === 0}>
          <summary>
            <strong>Del {e.desde} al {e.hasta}</strong> · {e.total_normas} normas · {e.total_proyectos} proyectos
            {e.enviado && " · enviado por correo"}
          </summary>
          {e.resumen?.panorama && (
            <>
              <h4>Resumen</h4>
              <p>{e.resumen.panorama}</p>
              <ul>{(e.resumen.puntos || []).map((p, k) => <li key={k}>{p}</li>)}</ul>
            </>
          )}
          {e.resumen?.error && <p className="ia-aviso">No se pudo generar el resumen: {e.resumen.error}</p>}
          <h4>Normas legales ({e.total_normas}{e.total_normas > (e.normas || []).length ? `, se muestran las ${(e.normas || []).length} más relevantes` : ""})</h4>
          <ul>
            {(e.normas || []).map((n, k) => (
              <li key={k}>
                {n.url ? <a href={n.url} target="_blank" rel="noopener noreferrer">{n.nombre}</a> : n.nombre} ({n.fecha}) — {n.sumilla}
              </li>
            ))}
          </ul>
          <h4>Proyectos de ley ({e.total_proyectos})</h4>
          <ul>
            {(e.proyectos || []).map((p, k) => (
              <li key={k}>
                {p.url ? <a href={p.url} target="_blank" rel="noopener noreferrer">{p.nombre}</a> : p.nombre} ({p.fecha}, {p.estado}) — {p.titulo}
              </li>
            ))}
          </ul>
          <p><a href={urlBuscador(b, e.desde, e.hasta)}>Ver todos los resultados de este periodo en el buscador →</a></p>
        </details>
      ))}
    </>
  );
}
