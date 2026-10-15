"use client";

import { useState } from "react";

export default function FormIngresar({ primero, volver }) {
  const [estado, setEstado] = useState("");
  const [error, setError] = useState("");

  async function enviar(e) {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.currentTarget).entries());
    if (primero && d.clave !== d.clave2) {
      setError("Las dos contraseñas no coinciden.");
      return;
    }
    setEstado("enviando");
    setError("");
    const r = await fetch("/api/sesion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accion: primero ? "primer_admin" : "ingresar", ...d }),
    });
    const res = await r.json().catch(() => ({ error: `Error del servidor (HTTP ${r.status})` }));
    if (!r.ok || res.error) {
      setError(res.error || "No se pudo ingresar.");
      setEstado("");
      return;
    }
    window.location.href = volver;
  }

  return (
    <form className="filtros" onSubmit={enviar}>
      {primero && (
        <label className="ancho">
          Nombre
          <input name="nombre" required placeholder="Ej.: Juan Martín" />
        </label>
      )}
      <label className="ancho">
        Usuario
        <input name="usuario" required autoComplete="username" placeholder={primero ? "Ej.: juanma" : ""} />
      </label>
      <label className="ancho">
        Contraseña{primero ? " (mínimo 8 caracteres)" : ""}
        <input name="clave" type="password" required autoComplete={primero ? "new-password" : "current-password"} />
      </label>
      {primero && (
        <label className="ancho">
          Repite la contraseña
          <input name="clave2" type="password" required autoComplete="new-password" />
        </label>
      )}
      <div className="acciones">
        <button className="boton" type="submit" disabled={estado === "enviando"}>
          {estado === "enviando" ? "Un momento…" : primero ? "Crear y entrar" : "Ingresar"}
        </button>
      </div>
      {error && <p className="ia-aviso ancho">{error}</p>}
    </form>
  );
}
