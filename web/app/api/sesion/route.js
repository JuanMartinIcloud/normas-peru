import { verificarUsuario, iniciarSesion, cerrarSesion, hayUsuarios, crearUsuario } from "../../../lib/auth";

export const dynamic = "force-dynamic";

// POST { accion: "ingresar" | "salir" | "primer_admin", usuario, clave, nombre }
export async function POST(request) {
  let c;
  try {
    c = await request.json();
  } catch {
    return Response.json({ error: "Pedido inválido" }, { status: 400 });
  }
  try {
    if (c.accion === "salir") {
      cerrarSesion();
      return Response.json({ ok: true });
    }
    if (c.accion === "primer_admin") {
      // Solo funciona mientras no exista ningun usuario
      if (await hayUsuarios()) return Response.json({ error: "Ya existe un administrador." }, { status: 403 });
      await crearUsuario({ usuario: c.usuario, nombre: c.nombre, clave: c.clave, rol: "admin" });
    }
    const u = await verificarUsuario(c.usuario, c.clave);
    if (!u) return Response.json({ error: "Usuario o contraseña incorrectos." }, { status: 401 });
    await iniciarSesion(u);
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: String(e.message || e) }, { status: 400 });
  }
}
