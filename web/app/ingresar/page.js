import { hayUsuarios } from "../../lib/auth";
import FormIngresar from "./FormIngresar";

export const metadata = { title: "Ingresar · Monitoreo empresarial" };

export default async function Ingresar({ searchParams }) {
  const volver = typeof searchParams?.volver === "string" && searchParams.volver.startsWith("/") ? searchParams.volver : "/monitoreo";
  let primero = false;
  let error = "";
  try {
    primero = !(await hayUsuarios());
  } catch (e) {
    error = "El sistema se está actualizando. Intenta de nuevo en unos minutos.";
  }
  return (
    <main className="contenedor angosto">
      <h1>{primero ? "Crear el administrador" : "Ingresar"}</h1>
      <p className="sub">
        {primero
          ? "Todavía no hay usuarios. Crea la cuenta del administrador: podrá crear las cuentas de los demás."
          : "Monitoreo empresarial: reportes de normas legales y del Congreso."}
      </p>
      {error ? <p className="ia-aviso">{error}</p> : <FormIngresar primero={primero} volver={volver} />}
    </main>
  );
}
