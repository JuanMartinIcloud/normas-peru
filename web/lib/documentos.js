import { createCipheriv } from "node:crypto";
import { parse } from "node-html-parser";

// Obtiene el texto completo de una norma (pagina de El Peruano) y el PDF de un proyecto de ley (Congreso)

const AGENTE = "Mozilla/5.0 (compatible; normas-peru/0.2; consulta de documentos publicos)";
const API_CONGRESO = "https://api.congreso.gob.pe/spley-portal-service";
// Clave publica que el propio portal del Congreso usa en el navegador para pedir un expediente
const CLAVE_PORTAL = Buffer.from("ProdALg5ZrAsxBMD", "utf8");
const MAX_PDF = 45 * 1024 * 1024;

async function pedir(url, opciones = {}, segundos = 60) {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), segundos * 1000);
  try {
    return await fetch(url, { ...opciones, signal: control.signal, cache: "no-store" });
  } finally {
    clearTimeout(reloj);
  }
}

// ---------------------------------------------------------------- El Peruano

// Devuelve el texto completo de la norma, o "" si no se pudo leer
export async function textoNorma(norma) {
  const url = norma.url_detalle;
  if (!url || !/^https:\/\/[a-z0-9.-]*elperuano\.pe\//i.test(url)) return "";
  const r = await pedir(url, { headers: { "User-Agent": AGENTE, Accept: "text/html" } });
  if (!r.ok) throw new Error(`El Peruano respondió HTTP ${r.status}`);
  const raiz = parse(await r.text());
  const cuerpo = raiz.querySelector("div.story") || raiz.querySelector("article");
  if (!cuerpo) return "";
  // Un parrafo por linea, sin espacios repetidos
  const bloques = cuerpo.querySelectorAll("p, h1, h2, h3, h4, li, td");
  const lineas = (bloques.length ? bloques : [cuerpo])
    .map((b) => b.text.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  return lineas.join("\n").slice(0, 300000);
}

// ---------------------------------------------------------------- Congreso

function cifrar(texto) {
  const c = createCipheriv("aes-128-ecb", CLAVE_PORTAL, null);
  const salida = Buffer.concat([c.update(String(texto), "utf8"), c.final()]).toString("base64");
  return salida.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

const CABECERAS_CONGRESO = {
  "User-Agent": AGENTE,
  Origin: "https://wb2server.congreso.gob.pe",
  Referer: "https://wb2server.congreso.gob.pe/",
  Accept: "application/json, text/plain, */*",
};

// Elige el archivo con el texto del proyecto: el que se adjunto al presentarlo, sin oficios de remision
function elegirArchivo(expediente) {
  const seguimientos = [...(expediente.seguimientos || [])].sort((a, b) =>
    String(a.fecha || "").localeCompare(String(b.fecha || ""))
  );
  const todos = seguimientos.flatMap((s) => (s.archivos || []).map((a) => ({ ...a, estado: s.desEstado })));
  const utiles = todos.filter((a) => a.proyectoArchivoId && a.activo !== false && a.publico !== false);
  const sinOficio = utiles.filter((a) => !/oficio|cargo|decreto de remisi/i.test(`${a.nombreArchivo} ${a.descripcion}`));
  return sinOficio[0] || utiles[0] || null;
}

// Devuelve { pdf: Buffer, nombre, sumilla } del proyecto; pdf puede ser null si el Congreso no tiene archivo
export async function documentoProyecto(p) {
  const url = `${API_CONGRESO}/expediente/${cifrar(p.periodo)}/${cifrar(p.num_pley)}?codTipoParl=${encodeURIComponent(p.camara || "C")}`;
  const r = await pedir(url, { headers: CABECERAS_CONGRESO });
  if (!r.ok) throw new Error(`El Congreso respondió HTTP ${r.status}`);
  const exp = ((await r.json()) || {}).data || {};
  const sumilla = (exp.general && exp.general.sumilla) || "";
  const archivo = elegirArchivo(exp);
  if (!archivo) return { pdf: null, nombre: "", sumilla };
  const codigo = Buffer.from(String(archivo.proyectoArchivoId)).toString("base64");
  const rp = await pedir(`${API_CONGRESO}/archivo/${codigo}/pdf`, { headers: CABECERAS_CONGRESO }, 90);
  if (!rp.ok) throw new Error(`No se pudo descargar el PDF del proyecto (HTTP ${rp.status})`);
  const pdf = Buffer.from(await rp.arrayBuffer());
  if (pdf.subarray(0, 4).toString("latin1") !== "%PDF") throw new Error("El Congreso no devolvió un PDF válido");
  if (pdf.length > MAX_PDF) throw new Error("El PDF del proyecto es demasiado grande (más de 45 MB)");
  return { pdf, nombre: archivo.nombreArchivo || `${p.numero}.pdf`, sumilla };
}
