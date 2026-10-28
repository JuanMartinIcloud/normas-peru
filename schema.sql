-- Esquema para Neon (PostgreSQL). Ejecutar una vez: psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS normas (
    id              BIGSERIAL PRIMARY KEY,
    fuente          TEXT        NOT NULL DEFAULT 'elperuano',
    fecha           DATE        NOT NULL,              -- fecha de publicacion
    tipo            TEXT,                              -- Ley, Decreto Supremo, Resolucion Ministerial...
    numero          TEXT,                              -- ej. 012-2026-MINSA
    entidad         TEXT,                              -- entidad emisora
    sector          TEXT,                              -- sector normalizado (Salud, Economia...)
    rubro           TEXT,                              -- rubro tematico
    sumilla         TEXT,
    url_pdf         TEXT,
    url_detalle     TEXT,
    extraordinaria  BOOLEAN     NOT NULL DEFAULT FALSE,
    texto_r2_key    TEXT,                              -- ruta del texto/PDF en Cloudflare R2 (opcional)
    hash_unico      TEXT        NOT NULL,              -- evita duplicados
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT normas_hash_unico UNIQUE (hash_unico)
);

CREATE INDEX IF NOT EXISTS idx_normas_fecha  ON normas (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_normas_tipo   ON normas (tipo);
CREATE INDEX IF NOT EXISTS idx_normas_sector ON normas (sector);
CREATE INDEX IF NOT EXISTS idx_normas_rubro  ON normas (rubro);

-- Buscador de texto en espanol sobre sumilla, numero y entidad
CREATE INDEX IF NOT EXISTS idx_normas_busqueda ON normas
    USING GIN (to_tsvector('spanish',
        coalesce(sumilla,'') || ' ' || coalesce(numero,'') || ' ' || coalesce(entidad,'')));

-- Punto de control: que dias ya se descargaron (permite reanudar el historico)
CREATE TABLE IF NOT EXISTS descargas (
    fecha       DATE PRIMARY KEY,
    estado      TEXT        NOT NULL,                  -- ok | vacio | error
    cantidad    INTEGER     NOT NULL DEFAULT 0,
    detalle     TEXT,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Proyectos de ley del Congreso (periodo 2021 en adelante, desde su portal oficial)
-- Migracion unica: si la tabla antigua (sin columna "camara") existe, se recrea. Estaba vacia.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'proyectos_ley')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'proyectos_ley' AND column_name = 'camara') THEN
        DROP TABLE proyectos_ley;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS proyectos_ley (
    id                 BIGSERIAL PRIMARY KEY,
    periodo            TEXT NOT NULL,            -- ej. 2021 (periodo parlamentario 2021-2026)
    camara             TEXT NOT NULL DEFAULT 'C',-- C = Congreso, D = Diputados, S = Senado
    numero             TEXT NOT NULL,            -- ej. 14864/2025-CR
    num_pley           INTEGER,
    fecha_presentacion DATE,
    titulo             TEXT,
    autor              TEXT,
    proponente         TEXT,
    comision           TEXT,
    estado             TEXT,
    rubro              TEXT,
    url                TEXT,
    actualizado        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (periodo, camara, numero)
);

CREATE INDEX IF NOT EXISTS idx_proy_fecha  ON proyectos_ley (fecha_presentacion DESC);
CREATE INDEX IF NOT EXISTS idx_proy_estado ON proyectos_ley (estado);
CREATE INDEX IF NOT EXISTS idx_proy_rubro  ON proyectos_ley (rubro);

-- ---------------------------------------------------------------------------
-- Etapa 3: resumenes diarios con IA.
-- Este mismo bloque lo ejecuta src/db.py automaticamente (asegurar_esquema),
-- asi que no hace falta correrlo a mano. Se puede repetir sin riesgo.
-- ---------------------------------------------------------------------------

-- Cuando aparecio cada proyecto en la base y cuando cambio de estado por ultima vez.
-- A los proyectos que ya existian se les pone como "aparicion" su fecha de presentacion.
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS creado_en TIMESTAMPTZ;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS estado_cambiado_en TIMESTAMPTZ;
UPDATE proyectos_ley
   SET creado_en = COALESCE(fecha_presentacion::timestamp AT TIME ZONE 'America/Lima', actualizado)
 WHERE creado_en IS NULL;
ALTER TABLE proyectos_ley ALTER COLUMN creado_en SET DEFAULT now();
ALTER TABLE proyectos_ley ALTER COLUMN creado_en SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proy_creado        ON proyectos_ley (creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_proy_estado_cambio ON proyectos_ley (estado_cambiado_en DESC);

-- Un resumen por dia de publicacion
CREATE TABLE IF NOT EXISTS resumenes (
    fecha          DATE PRIMARY KEY,                   -- dia que se resume (fecha de publicacion)
    datos          JSONB       NOT NULL,               -- resumen estructurado (ver src/resumen.py)
    modelo         TEXT,                               -- modelo de Gemini que lo escribio
    n_normas       INTEGER     NOT NULL DEFAULT 0,
    n_proyectos    INTEGER     NOT NULL DEFAULT 0,     -- proyectos nuevos incluidos
    n_cambios      INTEGER     NOT NULL DEFAULT 0,     -- proyectos que cambiaron de estado
    ventana_desde  TIMESTAMPTZ,                        -- rango usado para "proyectos nuevos" y "cambios"
    ventana_hasta  TIMESTAMPTZ,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Etapa 4: busqueda dentro del contenido.
-- Tambien la ejecuta src/db.py automaticamente. Se puede repetir sin riesgo.
-- ---------------------------------------------------------------------------

-- Proyectos: sumilla extensa del expediente del Congreso (explica que propone el proyecto)
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS sumilla TEXT;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS sumilla_revisada BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_proy_busqueda ON proyectos_ley
    USING GIN (to_tsvector('spanish', coalesce(titulo,'') || ' ' || coalesce(sumilla,'')));

-- Normas: palabras del texto completo (del PDF oficial). Se guardan solo las palabras
-- indexadas, no el texto, para no llenar la base gratuita.
ALTER TABLE normas ADD COLUMN IF NOT EXISTS texto_tsv tsvector;
ALTER TABLE normas ADD COLUMN IF NOT EXISTS texto_estado TEXT;   -- ok | sin_texto | sin_pdf
CREATE INDEX IF NOT EXISTS idx_normas_texto ON normas USING GIN (texto_tsv);

-- ---------------------------------------------------------------------------
-- Etapa 5: texto completo de todas las normas y proyectos (busqueda e IA).
-- El texto NO se guarda en esta base: va a las bases de texto (secretos TEXTOS_URL_1, _2...),
-- en la tabla "documentos" que crea src/indexar.py. Esta base solo se consulta al empezar.
-- Las columnas texto_estado/texto_base quedan de una version anterior y ya no se usan.
-- ---------------------------------------------------------------------------
ALTER TABLE normas ADD COLUMN IF NOT EXISTS texto_base SMALLINT;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS texto_estado TEXT;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS texto_base SMALLINT;

-- ---------------------------------------------------------------------------
-- Etapa 6: monitoreo empresarial (reportes para AmCham).
-- Tambien la ejecuta src/db.py automaticamente. Se puede repetir sin riesgo.
-- ---------------------------------------------------------------------------

-- Seguimiento de cada expediente del Congreso (dictamenes, remisiones al Senado, autografas...)
CREATE TABLE IF NOT EXISTS seguimientos (
    id           BIGINT PRIMARY KEY,          -- seguimientoPleyId del Congreso
    proyecto_id  INTEGER NOT NULL REFERENCES proyectos_ley(id) ON DELETE CASCADE,
    fecha        TIMESTAMPTZ NOT NULL,
    camara       CHAR(1),                     -- C Congreso, D Diputados, S Senado
    estado       TEXT,
    comisiones   TEXT,
    detalle      TEXT,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_seg_fecha    ON seguimientos (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_seg_proyecto ON seguimientos (proyecto_id);
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS camara_actual CHAR(1);
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS seguimiento_revisado TIMESTAMPTZ;

-- Analisis con IA de cada norma (tipo N) y proyecto de ley (tipo P)
CREATE TABLE IF NOT EXISTS analisis (
    id                BIGSERIAL PRIMARY KEY,
    tipo              CHAR(1) NOT NULL,
    ref_id            BIGINT NOT NULL,        -- normas.id o proyectos_ley.id
    fecha             DATE NOT NULL,          -- publicacion o presentacion
    relevante         BOOLEAN NOT NULL,
    resumen           TEXT,
    cambios           TEXT,
    comentario        TEXT,
    sector            TEXT,
    calificacion      TEXT,                   -- Favorable | Desfavorable | Para seguimiento
    impacto           TEXT,                   -- Alto | Moderado | Bajo
    comites           TEXT[],
    acciones          JSONB,                  -- [{comite, accion}]
    accion_directorio TEXT,
    lectura           TEXT,                   -- texto completo | sumilla
    modelo            TEXT,
    excluido          BOOLEAN NOT NULL DEFAULT FALSE,
    excluido_por      TEXT,
    excluido_en       TIMESTAMPTZ,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tipo, ref_id)
);
CREATE INDEX IF NOT EXISTS idx_analisis_fecha ON analisis (tipo, fecha DESC);

-- Usuarios del modulo de monitoreo
CREATE TABLE IF NOT EXISTS usuarios (
    id          SERIAL PRIMARY KEY,
    usuario     TEXT UNIQUE NOT NULL,
    nombre      TEXT,
    clave_hash  TEXT NOT NULL,
    rol         TEXT NOT NULL DEFAULT 'editor',   -- admin | editor
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ajustes internos (clave de sesiones, avance del analisis historico, correo...)
CREATE TABLE IF NOT EXISTS configuracion (
    clave       TEXT PRIMARY KEY,
    valor       TEXT,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Informe diario: aprobacion y envio
CREATE TABLE IF NOT EXISTS informes (
    fecha        DATE PRIMARY KEY,
    estado       TEXT NOT NULL DEFAULT 'borrador',   -- borrador | aprobado | enviado
    aprobado_por TEXT,
    aprobado_en  TIMESTAMPTZ,
    enviado_en   TIMESTAMPTZ,
    ejecutivo    JSONB,                              -- resumen ejecutivo generado por la IA
    actualizado  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Busqueda: proyectos hallados por su texto completo (clave periodo|camara|numero)
CREATE INDEX IF NOT EXISTS idx_proy_clave ON proyectos_ley ((periodo || '|' || camara || '|' || numero));

-- Etapa 7: puntaje de impacto (1 a 10) y version de los criterios de calificacion.
ALTER TABLE analisis ADD COLUMN IF NOT EXISTS puntaje SMALLINT;
ALTER TABLE analisis ADD COLUMN IF NOT EXISTS criterio SMALLINT;   -- version de los criterios usada (ver CRITERIO en src/monitoreo.py)
CREATE INDEX IF NOT EXISTS idx_analisis_criterio ON analisis (criterio) WHERE relevante;

-- Etapa 8: proposiciones convertidas en ley y vinculo entre camaras (ver src/leyes.py).
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS ley_tipo      TEXT;    -- Ley | Resolución Legislativa ...
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS ley_numero    TEXT;    -- numero de la ley publicada
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS ley_fecha     DATE;    -- publicacion en El Peruano
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS ley_docs      JSONB;   -- {"ley": {id, fecha, url}, "erratas": [{id, fecha, url}]}
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS enlace_id     INTEGER; -- la misma iniciativa en la otra camara
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS enlace_numero TEXT;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS enlace_camara CHAR(1);
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS enlace_estado TEXT;
CREATE INDEX IF NOT EXISTS idx_proy_ley ON proyectos_ley (ley_numero) WHERE ley_numero IS NOT NULL;
