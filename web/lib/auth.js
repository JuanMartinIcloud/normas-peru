import { createHmac, randomBytes, scrypt as _scrypt, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { cookies } from "next/headers";
import { consultar } from "./db";

// Acceso con usuario y contraseña para el modulo de monitoreo.
// - Las contraseñas se guardan cifradas (scrypt con sal), nunca en texto plano.
// - La sesion es una cookie firmada con una clave secreta que se genera sola y se guarda en la base.

const scrypt = promisify(_scrypt);
const COOKIE = "sesion";
const DURACION_DIAS = 7;

export async function cifrarClave(clave) {
  const sal = randomBytes(16);
  const hash = await scrypt(String(clave), sal, 64);
  return `scrypt$${sal.toString("hex")}$${hash.toString("hex")}`;
}

async function claveCorrecta(clave, guardado) {
  const [, salHex, hashHex] = String(guardado || "").split("$");
  if (!salHex || !hashHex) return false;
  const hash = await scrypt(String(clave), Buffer.from(salHex, "hex"), 64);
  const esperado = Buffer.from(hashHex, "hex");
  return esperado.length === hash.length && timingSafeEqual(esperado, hash);
}

let secretoCache = null;
async function secreto() {
  if (secretoCache) return secretoCache;
  const filas = await consultar(`SELECT valor FROM configuracion WHERE clave = 'clave_sesiones'`);
  if (filas.length) return (secretoCache = filas[0].valor);
  const nuevo = randomBytes(32).toString("hex");
  await consultar(
    `INSERT INTO configuracion (clave, valor) VALUES ('clave_sesiones', $1) ON CONFLICT (clave) DO NOTHING`,
    [nuevo]
  );
  const [f] = await consultar(`SELECT valor FROM configuracion WHERE clave = 'clave_sesiones'`);
  return (secretoCache = f.valor);
}

function firmar(datos, clave) {
  return createHmac("sha256", clave).update(datos).digest("hex");
}

export async function hayUsuarios() {
  const [f] = await consultar(`SELECT count(*)::int AS n FROM usuarios`);
  return f.n > 0;
}

// Devuelve el usuario si la contraseña es correcta
export async function verificarUsuario(usuario, clave) {
  const filas = await consultar(
    `SELECT id, usuario, nombre, rol, clave_hash FROM usuarios WHERE lower(usuario) = lower($1) AND activo`,
    [String(usuario || "").trim()]
  );
  if (!filas.length || !(await claveCorrecta(clave, filas[0].clave_hash))) return null;
  const { clave_hash, ...u } = filas[0];
  return u;
}

export async function crearUsuario({ usuario, nombre, clave, rol = "editor" }) {
  const u = String(usuario || "").trim().toLowerCase();
  if (!/^[a-z0-9._@-]{3,60}$/.test(u)) throw new Error("El usuario debe tener de 3 a 60 letras, números, punto, guion o @.");
  if (String(clave || "").length < 8) throw new Error("La contraseña debe tener al menos 8 caracteres.");
  const hash = await cifrarClave(clave);
  await consultar(
    `INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES ($1, $2, $3, $4)`,
    [u, String(nombre || "").trim() || u, hash, rol === "admin" ? "admin" : "editor"]
  );
}

// Crea la cookie de sesion (en rutas de API o acciones del servidor)
export async function iniciarSesion(u) {
  const exp = Date.now() + DURACION_DIAS * 86400000;
  const datos = `${u.id}.${exp}`;
  const token = `${datos}.${firmar(datos, await secreto())}`;
  cookies().set(COOKIE, token, {
    httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: DURACION_DIAS * 86400,
  });
}

export function cerrarSesion() {
  cookies().set(COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
}

// Usuario de la sesion actual, o null
export async function usuarioActual() {
  const token = cookies().get(COOKIE)?.value || "";
  const partes = token.split(".");
  if (partes.length !== 3) return null;
  const [id, exp, firma] = partes;
  if (!/^\d+$/.test(id) || Number(exp) < Date.now()) return null;
  const esperada = firmar(`${id}.${exp}`, await secreto());
  if (esperada.length !== firma.length || !timingSafeEqual(Buffer.from(esperada), Buffer.from(firma))) return null;
  const filas = await consultar(`SELECT id, usuario, nombre, rol FROM usuarios WHERE id = $1 AND activo`, [Number(id)]);
  return filas[0] || null;
}
