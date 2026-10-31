import { neon } from "@neondatabase/serverless";

// Registro de las bases del sistema (ver src/principal.py):
// - Principales: TEXTOS_URL_4, 9, 10 y 11, mas las que el sistema cree solo. Se usa una a la vez.
// - De texto: los demas TEXTOS_URL_<n> (la 1 retirada), mas las que el sistema cree solo.
// - Control: TEXTOS_URL_2. Tabla "principal" (cual se usa) y "bases_extra" (conexion de cada base,
//   incluidas las creadas automaticamente en Neon).

export const FIJAS_PRINCIPALES = [4, 9, 10, 11];
const URL_CONTROL = (process.env.TEXTOS_URL_2 || "").trim();
let reg = { t: 0, filas: null };

export function ejecutar(url, texto, params = []) {
  // cache: "no-store" impide que Next.js guarde respuestas viejas de la base
  const sql = neon(url, { fetchOptions: { cache: "no-store" } });
  // Versiones nuevas del paquete usan sql.query(texto, params); las 0.x aceptan sql(texto, params)
  if (typeof sql.query === "function") return sql.query(texto, params);
  return sql(texto, params);
}

export function urlEntorno(n) {
  return (process.env[`TEXTOS_URL_${n}`] || "").trim();
}

// Filas de bases_extra: [{ numero, rol, url }] (como mucho una lectura cada 5 minutos)
export async function registro() {
  if (reg.filas && Date.now() - reg.t < 300000) return reg.filas;
  if (!URL_CONTROL) return [];
  try {
    const filas = await ejecutar(URL_CONTROL, "SELECT numero, rol, url FROM bases_extra", []);
    reg = { t: Date.now(), filas: filas.map((f) => ({ numero: Number(f.numero), rol: f.rol, url: f.url })) };
  } catch (e) {
    if (!reg.filas) reg = { t: Date.now(), filas: [] };
  }
  return reg.filas;
}

export async function urlBase(n) {
  const e = urlEntorno(n);
  if (e) return e;
  const r = (await registro()).find((f) => f.numero === Number(n));
  return r ? r.url : "";
}

// Bases de texto: [{ numero, url }]
export async function basesTexto() {
  const lista = [];
  for (let i = 1; i <= 12; i++) {
    if (FIJAS_PRINCIPALES.includes(i)) continue;
    // La base 1 se lleno y quedo lenta; su contenido completo se copio a la base 12.
    if (i === 1 && urlEntorno(12)) continue;
    const url = urlEntorno(i);
    if (url) lista.push({ numero: i, url });
  }
  for (const r of await registro()) if (r.rol === "texto" && r.url) lista.push({ numero: r.numero, url: r.url });
  return lista;
}

export function urlControl() {
  return URL_CONTROL;
}
