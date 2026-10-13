import { consultar, leerFiltros, construirWhere, prepararBusqueda, corregirConsulta } from "../../lib/db";
import { fragmentos, claveProyecto } from "../../lib/textos";
import Fragmento from "../Fragmento";
import { leerFiltrosProyectos, whereProyectos } from "../../lib/proyectos";
import { urlProyecto } from "../../lib/resumenes";
import BotonResumir from "../BotonResumir";
import Marcar from "../Marcar";
import BotonAmpliar from "./BotonAmpliar";

export const metadata = { title: "Buscar en todo · Normas Legales del Perú" };

const MOSTRAR = 20;

function qs(f, extra = {}) {
  const p = new URLSearchParams();
  for (const k of ["q", "desde", "hasta", "t"]) if (f[k]) p.set(k, f[k]);
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function buscarTodo(fn, fp) {
  await Promise.all([prepararBusqueda(fn, "N"), prepararBusqueda(fp, "P")]);
  const wn = construirWhere(fn);
  const wp = whereProyectos(fp);
  const [a, b, c, d] = await Promise.all([
    consultar(
      `SELECT id::text AS id, fecha::text AS fecha, tipo, numero, entidad, sumilla, url_detalle, url_pdf, hash_unico
       FROM normas ${wn.where} ORDER BY fecha DESC, id DESC LIMIT ${MOSTRAR}`,
      wn.params
    ),
    consultar(`SELECT count(*)::int AS n FROM normas ${wn.where}`, wn.params),
    consultar(
      `SELECT id::text AS id, numero, periodo, camara, num_pley, url, fecha_presentacion::text AS fecha,
              titulo, sumilla, proponente, estado
       FROM proyectos_ley ${wp.where} ORDER BY fecha_presentacion DESC NULLS LAST, id DESC LIMIT ${MOSTRAR}`,
      wp.params
    ),
    consultar(`SELECT count(*)::int AS n FROM proyectos_ley ${wp.where}`, wp.params),
  ]);
  const terminos = [fn.q, ...fn.terminos];
  const [fragN, fragP] = await Promise.all([
    fragmentos("N", a.map((n) => n.hash_unico), terminos).catch(() => ({})),
    fragmentos("P", c.map(claveProyecto), terminos).catch(() => ({})),
  ]);
  return { normas: a, totalN: b[0].n, proyectos: c, totalP: d[0].n, fragN, fragP };
}

export default async function Buscar({ searchParams }) {
  const sp = searchParams || {};
  const base = { q: sp.q, desde: sp.desde, hasta: sp.hasta, t: sp.t };
  const fn = leerFiltros(base);
  const fp = leerFiltrosProyectos(base);
  const filtros = { q: fn.q, desde: fn.desde, hasta: fn.hasta, t: fn.terminos.join("|") };
  const hayBusqueda = Boolean(fn.q || fn.desde || fn.hasta);

  let normas = [];
  let proyectos = [];
  let totalN = 0;
  let totalP = 0;
  let error = "";
  let fragN = {};
  let fragP = {};
  let corregidaDe = "";
  if (hayBusqueda) {
    try {
      let r = await buscarTodo(fn, fp);
      // Sin resultados: puede ser una palabra mal escrita ("piscologica"); se corrige y se repite
      if (r.totalN + r.totalP === 0 && fn.q) {
        const nueva = await corregirConsulta(fn.q);
        if (nueva) {
          const gn = { ...fn, q: nueva, clavesTexto: undefined, avisoTexto: undefined };
          const gp = { ...fp, q: nueva, clavesTexto: undefined, avisoTexto: undefined };
          const otra = await buscarTodo(gn, gp);
          if (otra.totalN + otra.totalP > 0) {
            corregidaDe = fn.q;
            Object.assign(fn, gn);
            Object.assign(fp, gp);
            filtros.q = nueva;
            r = otra;
          }
        }
      }
      ({ normas, proyectos, totalN, totalP, fragN, fragP } = r);
    } catch (e) {
      error = String(e.message || e);
    }
  }

  return (
    <main className="contenedor">
      <h1>Buscar en todo</h1>
      <p className="sub">Normas legales y proyectos de ley a la vez. Puedes resumir lo encontrado con IA o seleccionar documentos para unirlos.</p>

      <nav className="atajos" aria-label="Secciones">
        <a className="atajo" href="/">Normas legales</a>
        <a className="atajo activo" href="/buscar">Buscar en todo</a>
        <a className="atajo" href="/proyectos">Proyectos de ley</a>
        <a className="atajo" href="/resumenes">Resúmenes diarios</a>
      </nav>

      <form className="filtros" method="get" action="/buscar">
        <label className="ancho">
          ¿Qué buscas?
          <input type="search" name="q" defaultValue={fn.q} placeholder="Ej.: violencia juvenil, teletrabajo, Ley 32513" />
        </label>
        <label>
          Desde
          <input type="date" name="desde" defaultValue={fn.desde} />
        </label>
        <label>
          Hasta
          <input type="date" name="hasta" defaultValue={fn.hasta} />
        </label>
        <div className="acciones">
          <button className="boton" type="submit">Buscar</button>
          <a className="boton sec" href="/buscar">Limpiar</a>
        </div>
      </form>

      {error && (
        <div className="error">
          <strong>No se pudo leer la base de datos.</strong>
          <p>{error}</p>
        </div>
      )}

      {hayBusqueda && !error && (
        <>
          {(fn.avisoTexto || fp.avisoTexto) && (
            <p className="ia-aviso">La búsqueda en el texto completo no respondió; se muestran solo las coincidencias en sumillas y títulos.</p>
          )}
          {corregidaDe && (
            <p className="ia-aviso">
              No hubo resultados para «{corregidaDe}». Se muestran los resultados para <strong>«{fn.q}»</strong>.
            </p>
          )}
          <p className="resumen">
            {totalN.toLocaleString("es-PE")} normas legales · {totalP.toLocaleString("es-PE")} proyectos de ley
          </p>
          {fn.terminos.length > 0 && (
            <p className="terminos">
              <span>Incluye también:</span>
              {fn.terminos.map((t) => (
                <a
                  key={t}
                  className="etq"
                  href={`/buscar${qs({ ...filtros, t: fn.terminos.filter((x) => x !== t).join("|") })}`}
                  title="Quitar este término"
                >
                  {t} ✕
                </a>
              ))}
              <a href={`/buscar${qs({ ...filtros, t: "" })}`}>Quitar todos</a>
            </p>
          )}
          {fn.q && fn.terminos.length === 0 && <BotonAmpliar q={fn.q} desde={fn.desde} hasta={fn.hasta} />}
          <BotonResumir ambito="ambos" filtros={filtros} cantidad={totalN + totalP} />

          <h2 className="seccion">Normas legales</h2>
          {normas.length === 0 ? (
            <p className="vacio">No hay normas para esta búsqueda.</p>
          ) : (
            <div className="lista">
              {normas.map((n) => {
                const nombre = [n.tipo, n.numero].filter(Boolean).join(" N° ");
                return (
                  <article className="norma" key={n.id}>
                    <div className="linea1">
                      <span className="titulo">{nombre}</span>
                      <span className="entidad">{n.entidad}</span>
                      <span className="fecha">{n.fecha}</span>
                    </div>
                    <p className="sumilla">{n.sumilla}</p>
                    <Fragmento texto={fragN[n.hash_unico]} />
                    <div className="etiquetas">
                      <Marcar tipo="N" id={n.id} etiqueta={`${nombre} (${n.fecha})`} />
                      <span className="enlaces">
                        {n.url_detalle && <a href={n.url_detalle} target="_blank" rel="noopener noreferrer">Ver</a>}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
          {totalN > normas.length && (
            <p className="mas"><a href={`/${qs(filtros)}`}>Ver las {totalN.toLocaleString("es-PE")} normas con más filtros →</a></p>
          )}

          <h2 className="seccion">Proyectos de ley</h2>
          {proyectos.length === 0 ? (
            <p className="vacio">No hay proyectos de ley para esta búsqueda.</p>
          ) : (
            <div className="lista">
              {proyectos.map((p) => (
                <article className="norma" key={p.id}>
                  <div className="linea1">
                    <span className="titulo">Proyecto {p.numero}</span>
                    <span className="entidad">{p.proponente}</span>
                    <span className="fecha">{p.fecha}</span>
                  </div>
                  <p className="sumilla">{p.titulo}</p>
                  {p.sumilla && <p className="entidad">{p.sumilla}</p>}
                  <Fragmento texto={fragP[claveProyecto(p)]} />
                  <div className="etiquetas">
                    <Marcar tipo="P" id={p.id} etiqueta={`Proyecto ${p.numero}`} />
                    {p.estado && <span className="etq">{p.estado}</span>}
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
              ))}
            </div>
          )}
          {totalP > proyectos.length && (
            <p className="mas"><a href={`/proyectos${qs(filtros)}`}>Ver los {totalP.toLocaleString("es-PE")} proyectos con más filtros →</a></p>
          )}
        </>
      )}
    </main>
  );
}
