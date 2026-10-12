import { consultar } from "../../../../lib/db";
import { textoNorma, documentoProyecto } from "../../../../lib/documentos";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const EP = "https://busquedas.elperuano.pe";
const AGENTE = { "User-Agent": "Mozilla/5.0 (compatible; normas-peru/0.2; consulta de documentos publicos)" };

// Revisa como responde la portada del buscador de El Peruano (solo direcciones fijas de ese sitio)
async function revisarBuscador() {
  const r = {};
  const inicio = await fetch(`${EP}/`, { headers: AGENTE, cache: "no-store" });
  const html = await inicio.text();
  r.portada = { estado: inicio.status, bytes: html.length };
  // La portada puede no responder; se usa la pagina de una norma para conocer el codigo del sitio
  const [n] = await consultar(
    `SELECT url_detalle FROM normas WHERE url_detalle LIKE 'https://busquedas.elperuano.pe/%' ORDER BY fecha DESC, id DESC LIMIT 1`
  );
  const pagina = await fetch(n.url_detalle, { headers: AGENTE, cache: "no-store" });
  const htmlNorma = await pagina.text();
  r.norma = { url: n.url_detalle, estado: pagina.status, bytes: htmlNorma.length };
  const archivos = [...new Set(htmlNorma.match(/\/assets\/[\w.()-]+\.js/g) || [])];
  r.archivos = archivos;
  r.codigo = {};
  for (const a of archivos.slice(0, 15)) {
    const js = await (await fetch(`${EP}${a}`, { headers: AGENTE, cache: "no-store" })).text();
    const pistas = [];
    const re = /buscar|search|query|navigate\(|\/api\/|fetch\(|https?:\/\/[\w.-]+/gi;
    let m;
    while ((m = re.exec(js)) && pistas.length < 40) {
      pistas.push(js.slice(Math.max(0, m.index - 150), m.index + 200));
      re.lastIndex = m.index + 200;
    }
    r.codigo[a] = { bytes: js.length, pistas };
  }
  return r;
}

// Revisa que la IA y la lectura de documentos completos funcionen desde Vercel (no gasta cupo de IA)
export async function GET(request) {
  if (new URL(request.url).searchParams.get("buscador") === "1") {
    try {
      return Response.json(await revisarBuscador(), { headers: { "Cache-Control": "no-store" } });
    } catch (e) {
      return Response.json({ error: String(e.message || e) });
    }
  }
  const r = { clave_gemini: Boolean((process.env.GEMINI_API_KEY || "").trim()) };
  try {
    const [n] = await consultar(
      `SELECT id, tipo, numero, url_detalle FROM normas WHERE url_detalle IS NOT NULL ORDER BY fecha DESC, id DESC LIMIT 1`
    );
    const inicio = Date.now();
    const texto = await textoNorma(n);
    r.el_peruano = { norma: `${n.tipo} ${n.numero}`, caracteres: texto.length, segundos: (Date.now() - inicio) / 1000, inicio: texto.slice(0, 120) };
  } catch (e) {
    r.el_peruano = { error: String(e.message || e) };
  }
  try {
    const [p] = await consultar(
      `SELECT id, numero, periodo, camara, num_pley FROM proyectos_ley ORDER BY fecha_presentacion DESC NULLS LAST, id DESC LIMIT 1`
    );
    const inicio = Date.now();
    const doc = await documentoProyecto(p);
    r.congreso = { proyecto: p.numero, archivo: doc.nombre, bytes: doc.pdf ? doc.pdf.length : 0, segundos: (Date.now() - inicio) / 1000 };
  } catch (e) {
    r.congreso = { error: String(e.message || e) };
  }
  return Response.json(r, { headers: { "Cache-Control": "no-store" } });
}
