// Cliente de la API de Google Gemini para la web (capa gratuita).
// Usa las variables de entorno de Vercel: GEMINI_API_KEY (obligatoria) y GEMINI_MODELOS (opcional).

const API = process.env.GEMINI_API_BASE || "https://generativelanguage.googleapis.com/v1beta";
const SUBIDA = "https://generativelanguage.googleapis.com/upload/v1beta/files";
const MODELOS_POR_DEFECTO = "gemini-flash-latest,gemini-3.5-flash-lite,gemini-2.5-flash";

export class ErrorIA extends Error {
  constructor(mensaje, estado = 502) {
    super(mensaje);
    this.estado = estado;
  }
}

function clave() {
  const k = (process.env.GEMINI_API_KEY || "").trim();
  if (!k) {
    throw new ErrorIA(
      "Falta la clave de Gemini en Vercel. Agrégala en Settings > Environment Variables con el nombre GEMINI_API_KEY y vuelve a publicar.",
      503
    );
  }
  return k;
}

function modelos() {
  return (process.env.GEMINI_MODELOS || MODELOS_POR_DEFECTO)
    .split(",")
    .map((m) => m.trim())
    .filter(Boolean);
}

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

function aJSON(texto) {
  const limpio = texto.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  return JSON.parse(limpio);
}

// Sube un PDF grande a Gemini (archivos de mas de ~15 MB no caben dentro del pedido)
async function subirArchivo(buffer, nombre, tipo = "application/pdf") {
  const k = clave();
  const inicio = await fetch(SUBIDA, {
    method: "POST",
    headers: {
      "x-goog-api-key": k,
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": String(buffer.length),
      "X-Goog-Upload-Header-Content-Type": tipo,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file: { display_name: nombre.slice(0, 100) } }),
    cache: "no-store",
  });
  const url = inicio.headers.get("x-goog-upload-url");
  if (!inicio.ok || !url) throw new ErrorIA(`No se pudo subir ${nombre} a Gemini (HTTP ${inicio.status})`);
  const fin = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Length": String(buffer.length),
      "X-Goog-Upload-Offset": "0",
      "X-Goog-Upload-Command": "upload, finalize",
    },
    body: buffer,
    cache: "no-store",
  });
  if (!fin.ok) throw new ErrorIA(`No se pudo subir ${nombre} a Gemini (HTTP ${fin.status})`);
  let archivo = (await fin.json()).file;
  // Gemini procesa el archivo unos segundos antes de poder usarlo
  for (let i = 0; i < 20 && archivo && archivo.state === "PROCESSING"; i++) {
    await esperar(2000);
    const r = await fetch(`${API}/${archivo.name}`, { headers: { "x-goog-api-key": k }, cache: "no-store" });
    archivo = await r.json();
  }
  if (!archivo || archivo.state === "FAILED") throw new ErrorIA(`Gemini no pudo procesar ${nombre}`);
  return { file_data: { mime_type: tipo, file_uri: archivo.uri } };
}

// Convierte un PDF en una "parte" del pedido: pequeño = dentro del pedido; grande = subido aparte.
// El pedido completo no puede pasar de 20 MB, por eso solo van dentro los de hasta 2 MB
// (como maximo se unen 6 documentos: 6 x 2 MB, mas lo que agrega la codificacion, cabe holgado).
export async function partePDF(buffer, nombre) {
  if (buffer.length <= 2 * 1024 * 1024) {
    return { inline_data: { mime_type: "application/pdf", data: buffer.toString("base64") } };
  }
  return subirArchivo(buffer, nombre);
}

/**
 * Pide a Gemini una respuesta JSON.
 * partes: lista de partes ({text}, {inline_data}, {file_data}).
 * Devuelve { datos, modelo }.
 */
export async function generarJSON({ instrucciones, partes, esquema, maxTokens = 16384 }) {
  const k = clave();
  const cuerpo = {
    systemInstruction: { parts: [{ text: instrucciones }] },
    contents: [{ role: "user", parts: partes }],
    generationConfig: {
      temperature: 0.2,
      maxOutputTokens: maxTokens,
      responseMimeType: "application/json",
      responseSchema: esquema,
    },
  };
  const errores = [];
  let hubo400 = false;
  const vueltas = [...modelos().map((m) => [m, true]), ...modelos().map((m) => [m, false])];
  for (const [modelo, conEsquema] of vueltas) {
    if (!conEsquema) {
      if (!hubo400) break;
      delete cuerpo.generationConfig.responseSchema;
    }
    for (let intento = 1; intento <= 3; intento++) {
      let r;
      try {
        r = await fetch(`${API}/models/${modelo}:generateContent`, {
          method: "POST",
          headers: { "x-goog-api-key": k, "Content-Type": "application/json" },
          body: JSON.stringify(cuerpo),
          cache: "no-store",
        });
      } catch (e) {
        errores.push(`${modelo}: ${e.message}`);
        await esperar(3000 * intento);
        continue;
      }
      if (r.ok) {
        try {
          const json = await r.json();
          const cand = (json.candidates || [])[0];
          const texto = ((cand && cand.content && cand.content.parts) || [])
            .filter((p) => !p.thought)
            .map((p) => p.text || "")
            .join("");
          if (!texto.trim()) throw new Error(`respuesta vacía (${cand ? cand.finishReason : "sin candidatos"})`);
          return { datos: aJSON(texto), modelo };
        } catch (e) {
          errores.push(`${modelo}: ${e.message}`);
          continue;
        }
      }
      const detalle = (await r.text()).slice(0, 300);
      errores.push(`${modelo}: HTTP ${r.status} ${detalle}`);
      if ([500, 502, 503, 504].includes(r.status)) {
        await esperar(4000 * intento);
        continue;
      }
      if ((r.status === 400 || r.status === 401 || r.status === 403) && /API key|API_KEY|credential/i.test(detalle)) {
        throw new ErrorIA("La clave GEMINI_API_KEY de Vercel no es válida.", 503);
      }
      if (r.status === 400) hubo400 = true;
      break; // 404 (modelo no existe), 429 (cupo agotado), 400: probar el siguiente modelo
    }
  }
  const cupo = errores.some((e) => /HTTP 429/.test(e));
  throw new ErrorIA(
    cupo
      ? "Se agotó por ahora el cupo gratuito de Gemini. Intenta en unos minutos."
      : `Gemini no respondió: ${errores.slice(-3).join(" | ")}`,
    cupo ? 429 : 502
  );
}
