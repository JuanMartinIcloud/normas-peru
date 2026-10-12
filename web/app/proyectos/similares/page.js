import { consultar } from "../../../lib/db";
import { urlProyecto } from "../../../lib/resumenes";
import Marcar from "../../Marcar";

export const metadata = { title: "Proyectos similares · Normas Legales del Perú" };

// Proyectos cuyo titulo comparte mas palabras importantes con el elegido
async function buscarSimilares(id) {
  const [base] = await consultar(
    `SELECT id::text AS id, numero, periodo, camara, num_pley, url, fecha_presentacion::text AS fecha,
            titulo, proponente, estado
     FROM proyectos_ley WHERE id = $1`,
    [id]
  );
  if (!base) return { base: null, similares: [] };
  const similares = await consultar(
    `WITH q AS (
       SELECT replace(plainto_tsquery('spanish', $1)::text, ' & ', ' | ')::tsquery AS consulta
     )
     SELECT p.id::text AS id, p.numero, p.periodo, p.camara, p.num_pley, p.url,
            p.fecha_presentacion::text AS fecha, p.titulo, p.proponente, p.estado,
            ts_rank_cd(to_tsvector('spanish', coalesce(p.titulo,'')), q.consulta, 1) AS parecido
     FROM proyectos_ley p, q
     WHERE p.id <> $2 AND numnode(q.consulta) > 0
       AND to_tsvector('spanish', coalesce(p.titulo,'')) @@ q.consulta
     ORDER BY parecido DESC, p.fecha_presentacion DESC NULLS LAST
     LIMIT 25`,
    [base.titulo || "", id]
  );
  return { base, similares };
}

function Tarjeta({ p, extra }) {
  return (
    <article className="norma">
      <div className="linea1">
        <span className="titulo">Proyecto {p.numero}</span>
        <span className="entidad">{p.proponente}</span>
        <span className="fecha">{p.fecha}</span>
      </div>
      <p className="sumilla">{p.titulo}</p>
      <div className="etiquetas">
        <Marcar tipo="P" id={p.id} etiqueta={`Proyecto ${p.numero}`} />
        {p.estado && <span className="etq">{p.estado}</span>}
        {extra}
        <span className="enlaces">
          <a href={`/proyectos/similares?id=${p.id}`}>Similares</a>
          {urlProyecto(p) && (
            <>
              {" · "}
              <a href={urlProyecto(p)} target="_blank" rel="noopener noreferrer">Expediente</a>
            </>
          )}
        </span>
      </div>
    </article>
  );
}

export default async function Similares({ searchParams }) {
  const id = /^\d{1,18}$/.test(String(searchParams?.id || "")) ? String(searchParams.id) : "";
  let datos = { base: null, similares: [] };
  let error = "";
  if (id) {
    try {
      datos = await buscarSimilares(id);
    } catch (e) {
      error = String(e.message || e);
    }
  }
  const maximo = Math.max(...datos.similares.map((s) => Number(s.parecido) || 0), 0);

  return (
    <main className="contenedor">
      <h1>Proyectos similares</h1>
      <p className="sub">
        Proyectos cuyo título trata lo mismo que el elegido. Marca los que quieras y pulsa «Proponer proyecto unificado» en la barra de abajo.
      </p>
      <nav className="atajos" aria-label="Secciones">
        <a className="atajo" href="/proyectos">← Proyectos de ley</a>
        <a className="atajo" href="/buscar">Buscar en todo</a>
      </nav>

      {error && (
        <div className="error">
          <strong>No se pudo leer la base de datos.</strong>
          <p>{error}</p>
        </div>
      )}
      {!error && !datos.base && <p className="vacio">No se encontró el proyecto.</p>}
      {datos.base && (
        <>
          <h2 className="seccion">Proyecto elegido</h2>
          <div className="lista">
            <Tarjeta p={datos.base} />
          </div>
          <h2 className="seccion">Parecidos ({datos.similares.length})</h2>
          {datos.similares.length === 0 ? (
            <p className="vacio">No se encontraron proyectos parecidos.</p>
          ) : (
            <div className="lista">
              {datos.similares.map((p) => (
                <Tarjeta
                  key={p.id}
                  p={p}
                  extra={
                    <span className="etq gris">
                      Parecido {maximo ? Math.round((Number(p.parecido) / maximo) * 100) : 0}%
                    </span>
                  }
                />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
