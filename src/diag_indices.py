"""Diagnostico temporal: probar cada modelo de reserva con un analisis real."""
import sys; sys.path.insert(0, "src")
import gemini, monitoreo
cab = "Norma: DECRETO SUPREMO que modifica el Reglamento de la Ley del Impuesto a la Renta para deducciones de gastos de capacitacion."
for m in ["gemma-4-31b-it", "gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-3-flash-preview"]:
    try:
        d, mod = gemini.generar_json(monitoreo._analisis_instr(), cab, monitoreo.ANALISIS_ESQUEMA, [m], 4096)
        print(m, "OK", mod, monitoreo._limpia(d)["calificacion"], monitoreo._limpia(d)["resumen"][:100])
    except Exception as e:
        print(m, "FALLA", str(e)[:300])
print("defecto:", gemini.modelos())
