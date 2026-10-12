import { consultar, leerFiltros, construirWhere, hoyLima, POR_PAGINA } from "../lib/db";
import { cargarResumen, ayerLima } from "../lib/resumenes";
import ResumenIA from "./ResumenIA";

export const dynamic = "force-dynamic";

// Construye una direccion conservando los filtros actuales y cambiando lo indicado
function enlace(f, cambios = {}) {
  const base = { ...f, ...cambios };
  const qs = new URLSearchParams();
  for (const k of ["q", "fecha", "desde", "hasta", "anio", "sector", "rubro", "tipo"]) {
    if (base[k]) qs.set(k, base[k]);
  }
  if (base.central) qs.set("central", "1");
  if (base.leyes) qs.set("leyes", "1");
  if (base.pagina && base.pagina > 1) qs.set("p", String(base.pagina));
  const s = qs.toString();
  return s ? `/?${s}` : "/";
}

async function cargar(f) {
  const { where, params } = construirWhere(f);
  const offset = (f.pagina - 1) * POR_PAGINA;

  const [resumen, anios, sectores, rubros, tipos, filas, total] = await Promise.all([
    consultar(`SELECT count(*)::int AS total, min(fecha)::text AS primera, max(fecha)::text AS ultima FROM normas`),
    consultar(`SELECT extract(year FROM fecha)::int AS anio, count(*)::int AS n FROM normas GROUP BY 1 ORDER BY 1 DESC`),
    consultar(`SELECT sector AS valor, count(*)::int AS n FROM normas WHERE sector IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT rubro AS valor, count(*)::int AS n FROM normas WHERE rubro IS NOT NULL GROUP BY 1 ORDER BY 2 DESC`),
    consultar(`SELECT tipo AS valor, count(*)::int AS n FROM normas WHERE tipo IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 40`),
    consultar(
      `SELECT id, fecha::text AS fecha, tipo, numero, entidad, sector, rubro, sumilla, url_pdf, url_detalle, extraordinaria
       FROM normas ${where} ORDER BY fecha DESC, id DESC LIMIT ${POR_PAGINA} OFFSET ${offset}`,
      params
    ),
    consultar(`SELECT count(*)::int AS n FROM normas ${where}`, params),
  ]);

  return { resumen: resumen[0], anios, sectores, rubros, tipos, filas, total: total[0].n };
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

export default async function Pagina({ searchParams }) {
  const sp = { ...(searchParams || {}) };
  if (sp.fecha === "hoy") sp.fecha = hoyLima();
  const f = leerFiltros(sp);

  let datos;
  try {
    datos = await cargar(f);
  } catch (e) {
    return (
      <main className="contenedor">
        <h1>Normas Legales del Perú</h1>
        <div className="error">
          <strong>No se pudo leer la base de datos.</strong>
          <p>{String(e.message || e)}</p>
          <p>Revisa que la variable DATABASE_URL esté puesta en Vercel y que las tablas existan en Neon.</p>
        </div>
      </main>
    );
  }

  const { resumen, anios, sectores, rubros, tipos, filas, total } = datos;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const hoy = hoyLima();
  const csv = enlace(f, { pagina: 1 }).replace("/?", "/api/csv?").replace(/^\/$/, "/api/csv");
  const hayFiltros =
    f.q || f.fecha || f.desde || f.hasta || f.anio || f.sector || f.rubro || f.tipo || f.central || f.leyes;

  // Resumen con IA: solo en la portada (sin filtros, primera pagina).
  // Si falla, la pagina sigue funcionando sin el resumen.
  let resumenIA = null;
  if (!hayFiltros && f.pagina === 1) {
    try {
      resumenIA = await cargarResumen();
    } catch (e) {
      resumenIA = null;
    }
  }
  const ayer = ayerLima();

  return (
    <main className="contenedor">
      <h1>Normas Legales del Perú</h1>
      <p className="sub">
        {resumen.total.toLocaleString("es-PE")} normas guardadas
        {resumen.primera ? ` · desde ${resumen.primera} hasta ${resumen.ultima}` : ""}
      </p>

      <nav className="atajos" aria-label="Atajos">
        <a className={`atajo ${f.fecha === hoy ? "activo" : ""}`} href={enlace({}, { fecha: hoy })}>Hoy</a>
        <a className={`atajo ${!hayFiltros ? "activo" : ""}`} href="/">Más recientes</a>
        <a className={`atajo ${f.leyes ? "activo" : ""}`} href={enlace(f, { leyes: !f.leyes, pagina: 1 })}>
          Leyes y normas con rango de ley
        </a>
        <a className={`atajo ${f.central ? "activo" : ""}`} href={enlace(f, { central: !f.central, pagina: 1 })}>
          Solo gobierno central
        </a>
        <a className="atajo" href="/resumenes">Resúmenes diarios</a>
        <a className="atajo" href="/proyectos">Proyectos de ley →</a>
      </nav>

      {!hayFiltros && f.pagina === 1 && (
        <>
          {(!resumenIA || resumenIA.fecha < ayer) && (
            <p className="ia-pendiente">
              El resumen con IA de lo publicado ayer se prepara cada madrugada y estará listo antes de las 8:00 a. m.
              {resumenIA ? " Mientras tanto, este es el último disponible." : ""}
            </p>
          )}
          {resumenIA && <ResumenIA resumen={resumenIA} />}
        </>
      )}

      {anios.length > 0 && (
        <div className="panel">
          <h2>Por año</h2>
          <div className="anios">
            {anios.map((a) => (
              <a
                key={a.anio}
                className={`atajo ${f.anio === String(a.anio) ? "activo" : ""}`}
                href={enlace({ central: f.central }, { anio: String(a.anio) })}
              >
                {a.anio} · {a.n.toLocaleString("es-PE")}
              </a>
            ))}
          </div>
        </div>
      )}

      <form className="filtros" method="get" action="/">
        <label className="ancho">
          Buscar por palabra, número o entidad
          <input type="search" name="q" defaultValue={f.q} placeholder="Ej.: transferencia de partidas, 505-2026, MINSA" />
        </label>
        <label>
          Rubro
          <select name="rubro" defaultValue={f.rubro}><Opciones lista={rubros} /></select>
        </label>
        <label>
          Sector
          <select name="sector" defaultValue={f.sector}><Opciones lista={sectores} /></select>
        </label>
        <label>
          Tipo de norma
          <select name="tipo" defaultValue={f.tipo}><Opciones lista={tipos} /></select>
        </label>
        <label>
          Fecha exacta
          <input type="date" name="fecha" defaultValue={f.fecha} />
        </label>
        <label>
          Desde
          <input type="date" name="desde" defaultValue={f.desde} />
        </label>
        <label>
          Hasta
          <input type="date" name="hasta" defaultValue={f.hasta} />
        </label>
        <label className="check ancho">
          <input type="checkbox" name="central" value="1" defaultChecked={f.central} />
          Solo gobierno central (excluye municipalidades y gobiernos regionales)
        </label>
        <label className="check ancho">
          <input type="checkbox" name="leyes" value="1" defaultChecked={f.leyes} />
          Solo leyes y normas con rango de ley (leyes, decretos legislativos, decretos de urgencia, resoluciones legislativas)
        </label>
        <div className="acciones">
          <button className="boton" type="submit">Buscar</button>
          <a className="boton sec" href="/">Limpiar</a>
          <a className="boton sec" href={csv}>Descargar en Excel (CSV)</a>
        </div>
      </form>

      <p className="resumen">
        {total.toLocaleString("es-PE")} resultados · página {f.pagina} de {paginas.toLocaleString("es-PE")}
      </p>

      {filas.length === 0 ? (
        <p className="vacio">
          No hay normas para esta búsqueda.
          {f.fecha === hoy && " Las normas del día se cargan automáticamente por la noche y se revisan de nuevo de madrugada."}
        </p>
      ) : (
        <div className="lista">
          {filas.map((n) => (
            <article className="norma" key={n.id}>
              <div className="linea1">
                <span className="titulo">{[n.tipo, n.numero].filter(Boolean).join(" N° ")}</span>
                <span className="entidad">{n.entidad}</span>
                <span className="fecha">{n.fecha}</span>
              </div>
              <p className="sumilla">{n.sumilla}</p>
              <div className="etiquetas">
                {n.rubro && <span className="etq">{n.rubro}</span>}
                {n.sector && <span className="etq gris">{n.sector}</span>}
                {n.extraordinaria && <span className="etq gris">Edición extraordinaria</span>}
                <span className="enlaces">
                  {n.url_detalle && <a href={n.url_detalle} target="_blank" rel="noopener noreferrer">Ver</a>}
                  {n.url_pdf && (
                    <>
                      {" · "}
                      <a href={n.url_pdf} target="_blank" rel="noopener noreferrer">PDF</a>
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
