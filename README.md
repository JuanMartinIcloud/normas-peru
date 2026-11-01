# Normas legales del Perú

Sistema interno que descarga a diario las normas legales de El Peruano y los proyectos de ley del Congreso,
los guarda en bases de datos de Neon, los resume y analiza con IA (Gemini) y los muestra en una web privada
(Vercel). Todo funciona con planes gratuitos.

## Partes

| Parte | Dónde | Qué hace |
|---|---|---|
| Tareas automáticas | GitHub Actions (`.github/workflows/`, código en `src/`) | Descargan, clasifican, resumen, analizan e indexan |
| Base principal | Neon, secreto `TEXTOS_URL_4` | Normas, proyectos, seguimiento, análisis, resúmenes, usuarios |
| Bases de texto | Neon, secretos `TEXTOS_URL_2`, `3`, `5` a `12` | Texto completo de normas y proyectos (tabla `documentos`). La 1 está retirada. La 2 es además la base de control (cupos y avance de la indexación) |
| Web | Vercel, carpeta `web/` (Next.js) | Buscador, proyectos, resúmenes, monitoreo empresarial. Exige usuario y contraseña |

## Tareas automáticas

El flujo **Programador de tareas** (`programador.yml`) es el único que lanza las tareas diarias, a su hora
de Lima, y repite una tarea que falló (hasta 6 veces en el día). Corre solo en las horas en que hay tareas:
cada hora de 10:45 p. m. a 7:45 a. m., y a las 3:05 y 4:05 p. m. Los demás flujos no tienen horario propio.

| Hora (Lima) | Flujo | Qué hace |
|---|---|---|
| 22:40 | `diario.yml` | Normas del día (y del anterior, por ediciones extraordinarias) |
| 23:30 | `historico.yml` | Días pendientes del archivo histórico de El Peruano |
| 01:20 | `congreso.yml` | Proyectos de ley, su seguimiento y las leyes publicadas |
| 02:20 | `monitoreo.yml` | Análisis con IA del mes en curso y de lo pedido desde la web |
| 03:20 | `resumen.yml` | Resumen diario con IA |
| 04:00 | `indexar.yml` | Texto completo de lo nuevo (solo lo que aún no está guardado) |
| 05:00 | `busquedas.yml` | Búsquedas guardadas que tocan ese día |
| 05:30 | `ocr.yml` | Lectura de documentos escaneados, si hay pendientes |
| 06:00 | `vigilar.yml` | Alarma de consumo de Neon (espacio, cómputo y transferencia) |
| 15:00 | `recalificar.yml` | Recalificación pendiente del monitoreo, si hay |
| lunes 06:10 | `vocabulario.yml` | Vocabulario del corrector de búsquedas |

Otros flujos:

- **Cupos de Neon** (`cupos.yml`, 4 veces al día: 10 p. m., 2 a. m., 5 a. m. y 1 p. m.): mide con la API de
  Neon cuántos datos salieron de cada base en el mes. Ver «Límites de Neon».

## Monitoreo a pedido

La IA revisa sola cada madrugada el mes en curso. Los meses anteriores se revisan a pedido: al abrir un mes
en el monitoreo aparece «Revisar este mes con IA». También se piden solos los documentos de una búsqueda
guardada que la IA aún no revisó, y los que alguien pasa a mano a «impacto empresarial» (esos quedan en el
reporte aunque la IA los vuelva a revisar). Los pedidos se guardan en la tabla `analisis_pedidos` y los
atiende `monitoreo.py pedidos`: al momento si Vercel tiene la variable `GITHUB_TAREAS` (clave de GitHub que
solo puede lanzar tareas de este repositorio); si no, en la ejecución de la madrugada.
- **Diagnóstico** (`diagnostico.yml`, a mano): mediciones de solo lectura.
- **Reconstruir la base principal** (`reconstruir.yml`, a mano): llena una base principal nueva desde las
  fuentes oficiales.

Las tablas se crean y actualizan solas la primera vez que corre cualquier tarea (`asegurar_esquema` en
`src/db.py`, a partir de `schema.sql`).

## Límites de Neon (plan gratuito, por base)

- Espacio: 1 GB. Las bases de texto se llenan hasta 900 MB y la indexación pasa sola a la siguiente.
- Transferencia: 5 GB al mes (datos que salen de la base). Se renueva el día 1 a las 00:00 hora universal
  (7:00 p. m. del día anterior en Lima).
  - Base principal en 4 GB: se detienen las tareas no indispensables.
  - Base principal en 4,6 GB: se detienen todas las tareas automáticas; lo que queda es para la web.
    Lo pendiente se completa solo cuando se renueva el cupo.
  - Base de texto en 4 GB: no se le agrega nada más ese mes.
- Cómputo: 100 horas al mes.

La web guarda el resultado de cada consulta un tiempo (listas y conteos 30 minutos; años, sectores y otros
catálogos 6 horas): una misma consulta no se vuelve a pedir a la base mientras su resultado esté vigente.

## Web

- Todo el sitio exige usuario y contraseña. Las cuentas las crea el administrador en *Monitoreo → Usuarios*.
- Tras 10 contraseñas equivocadas en 15 minutos se bloquean los intentos por 15 minutos.
- Robots y buscadores no tienen acceso (respuesta 403 y `robots.txt` que lo prohíbe todo).
- Descargas en Excel: hasta 5.000 filas. Listados: hasta la página 100.

Variables de entorno en Vercel: `TEXTOS_URL_2` a `TEXTOS_URL_12` (las mismas cadenas de las bases),
`GEMINI_API_KEY` (y opcional `GEMINI_MODELOS`), `GITHUB_TAREAS` (opcional, ver «Monitoreo a pedido») y
para el correo `CORREO_SERVIDOR`, `CORREO_USUARIO`, `CORREO_CLAVE`.

## Secretos de GitHub Actions

`TEXTOS_URL_2` a `TEXTOS_URL_12`, `GEMINI_API_KEY`, `NEON_API_KEY` (clave de la cuenta de Neon, para medir
cupos y consumo). Variable opcional: `GEMINI_MODELOS`.

Las cadenas de conexión y las claves solo van en los secretos de GitHub y en las variables de Vercel; nunca
en el código ni en mensajes.

## Agregar una base de texto

1. Crear un proyecto gratuito en Neon y copiar su cadena de conexión.
2. Agregarla como secreto `TEXTOS_URL_<número siguiente>` en GitHub y como variable con el mismo nombre en
   Vercel; agregar ese secreto a los flujos que usan las bases de texto (`indexar.yml`, `ocr.yml`,
   `monitoreo.yml`, `cupos.yml`, `vigilar.yml`) y subir el número máximo en `src/bases.py` y `web/lib/bases.js` si pasa de 12.
