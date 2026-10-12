import { consultar, leerFiltros, construirWhere, hoyLima } from "../../../lib/db";

export const dynamic = "force-dynamic";

const LIMITE = 50000;
const COLUMNAS = ["fecha", "tipo", "numero", "entidad", "sector", "rubro", "sumilla", "url_pdf", "url_detalle", "extraordinaria"];

function celda(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).replace(/\r?\n/g, " ");
  return /[",;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export async function GET(request) {
  const url = new URL(request.url);
  const sp = Object.fromEntries(url.searchParams.entries());
  if (sp.fecha === "hoy") sp.fecha = hoyLima();
  const f = leerFiltros(sp);
  const { where, params } = construirWhere(f);

  try {
    const filas = await consultar(
      `SELECT fecha::text AS fecha, tipo, numero, entidad, sector, rubro, sumilla, url_pdf, url_detalle, extraordinaria
       FROM normas ${where} ORDER BY fecha DESC, id DESC LIMIT ${LIMITE}`,
      params
    );
    const lineas = [COLUMNAS.join(",")];
    for (const r of filas) lineas.push(COLUMNAS.map((c) => celda(r[c])).join(","));
    // BOM para que Excel abra bien las tildes
    const cuerpo = "﻿" + lineas.join("\r\n");
    return new Response(cuerpo, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="normas-legales.csv"',
      },
    });
  } catch (e) {
    return new Response(`Error: ${e.message}`, { status: 500 });
  }
}
