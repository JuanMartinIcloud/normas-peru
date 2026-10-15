import { redirect } from "next/navigation";
import { usuarioActual } from "../../lib/auth";
import BotonSalir from "./BotonSalir";

export const metadata = { title: "Monitoreo empresarial" };

// Todo el modulo exige haber ingresado con usuario y contraseña
export default async function LayoutMonitoreo({ children }) {
  let u = null;
  try {
    u = await usuarioActual();
  } catch (e) {
    u = null;
  }
  if (!u) redirect("/ingresar?volver=/monitoreo");
  return (
    <main className="contenedor">
      <div className="barra-mon">
        <strong>Monitoreo empresarial</strong>
        <span className="usuario-mon">
          {u.nombre} · <BotonSalir />
        </span>
      </div>
      <nav className="atajos" aria-label="Monitoreo">
        <a className="atajo" href="/monitoreo">Resumen ejecutivo</a>
        <a className="atajo" href="/monitoreo/normas">Normas legales</a>
        <a className="atajo" href="/monitoreo/congreso">Congreso</a>
        <a className="atajo" href="/monitoreo/impacto">Impacto</a>
        <a className="atajo" href="/monitoreo/informe">Informe y envío</a>
        {u.rol === "admin" && <a className="atajo" href="/monitoreo/usuarios">Usuarios</a>}
        <a className="atajo" href="/">Buscador →</a>
      </nav>
      {children}
    </main>
  );
}
