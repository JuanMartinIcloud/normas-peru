# Normas legales del Perú → Neon

Descarga las normas legales de El Peruano, las clasifica por sector y rubro y las guarda en Neon (PostgreSQL).
Etapa 1: normas de El Peruano. Etapa 2: proyectos de ley del Congreso (todas las cámaras y proponentes). Etapa 3: resumen diario con IA.

## Estado

- **Listo:** esquema SQL, clasificador por reglas, cliente de descarga, carga diaria y carga histórica con punto de control, flujos de GitHub Actions.
- **Pendiente de confirmar:** el endpoint exacto de El Peruano. Su página carga el listado por JavaScript y no pude verlo desde mi entorno. Por eso el scraper es configurable y hay un sondeo que lo descubre.
- **No probado contra la fuente real.** La primera ejecución puede requerir ajustes en `src/config.py`.

## Puesta en marcha

1. **Neon:** crea un proyecto gratis en neon.tech, copia la cadena de conexión y ejecuta `psql "$DATABASE_URL" -f schema.sql`.
2. **GitHub:** sube esta carpeta a un repositorio. Los repos públicos tienen más minutos de Actions que los privados (revisa los límites vigentes).
3. En *Settings → Secrets and variables → Actions* agrega el secreto `DATABASE_URL`.
4. **Sondeo:** ejecuta el flujo *Sondeo de la fuente*, o en tu computadora `python src/probe.py`. Descarga los artefactos y busca el endpoint (otra vía: Chrome → F12 → Network → Fetch/XHR → pulsa *Buscar* en la página de Normas y copia la URL y los parámetros).
5. Carga en *Variables* de Actions: `ELPERUANO_ENDPOINT`, `ELPERUANO_METODO`, `ELPERUANO_PARAM_DESDE`, `ELPERUANO_PARAM_HASTA`. Si el JSON usa otros nombres de campo, ajusta `CAMPOS` en `src/config.py`.
6. **Prueba sin escribir en la base:** `python src/run_dia.py 2026-10-09 --sin-bd`
7. Si se ve bien, activa los flujos:
   - *Descarga diaria*: corre sola cada noche.
   - *Carga histórica*: tandas de hasta ~5,5 horas que se reanudan solas. Cambia `desde` para ir más atrás de 2019.

## Cómo funciona el histórico

`backfill.py` va del día más reciente hacia atrás y anota cada día en la tabla `descargas`. Si se corta, la siguiente tanda continúa donde quedó. Los días con error se reintentan.

## Almacenamiento

Neon gratis tiene poco espacio (revisa el límite vigente). Aquí solo se guardan metadatos y enlaces al PDF. Si luego quieres guardar PDFs o textos completos, la columna `texto_r2_key` está reservada para Cloudflare R2.

## Alcance y límites

- "Todo desde el inicio" depende de lo que El Peruano publique en línea. Lo anterior a su archivo digital puede estar solo en SPIJ (MINJUS), que habrá que evaluar aparte y revisando sus términos de uso.
- Respeta los términos de uso de cada sitio. La pausa entre solicitudes está en `PAUSA_SEGUNDOS` (1,5 s por defecto).
- La clasificación es por reglas (entidad y palabras clave). Lo que no calza queda como `Otros` o `Sin clasificar`, y se puede refinar después, con IA si quieres.

## Resumen diario con IA (Gemini)

Cada madrugada el flujo *Resumen diario con IA* (`.github/workflows/resumen.yml`, `src/resumen.py`):

1. Vuelve a descargar las normas de ayer (recoge ediciones extraordinarias tardías) y actualiza los proyectos del Congreso.
2. Envía a Gemini las sumillas de las normas de ayer, los proyectos de ley nuevos y los que cambiaron de estado.
3. Guarda el resultado en la tabla `resumenes`; la portada de la web lo muestra y `/resumenes` guarda el historial.

Se ejecuta a las 3:17, 5:17 y 7:17 a. m. (Lima). Los dos últimos son respaldos por si GitHub se retrasa: si el resumen ya existe, terminan sin hacer nada. Si falta algún día de la última semana, lo completa.

Requiere el secreto `GEMINI_API_KEY` (clave gratuita de Google AI Studio) en *Settings → Secrets and variables → Actions*. Opcional: la variable `GEMINI_MODELOS` para cambiar los modelos (por defecto `gemini-flash-latest,gemini-3.5-flash-lite,gemini-2.5-flash`).

La base se actualiza sola la primera vez que corre cualquier script (`asegurar_esquema` en `src/db.py`).

## Siguientes etapas

1. Descarga de PDFs a R2 y resúmenes basados en el texto completo de cada norma.

## Web (Vercel)

La carpeta `web/` es una página Next.js que lee la base de Neon: atajo "Hoy", año, rubro, sector, tipo, fechas, buscador y descarga CSV para Excel.

1. En Vercel: *Add New > Project*, importar este repositorio.
2. En *Root Directory* elegir `web`.
3. En *Environment Variables* agregar `DATABASE_URL` con la misma cadena de Neon.
4. *Deploy*.
