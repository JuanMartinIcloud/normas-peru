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
-- Tambien la ejecuta src/db.py automaticamente. Se puede repetir sin riesgo.
-- El texto se guarda en la tabla "textos" de esta base y, cuando se llena, en bases
-- adicionales (secretos TEXTOS_URL_1, TEXTOS_URL_2...). En cada documento se anota en que base quedo.
-- ---------------------------------------------------------------------------
ALTER TABLE normas ADD COLUMN IF NOT EXISTS texto_base SMALLINT;
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS texto_estado TEXT;   -- ok | sin_texto | sin_pdf
ALTER TABLE proyectos_ley ADD COLUMN IF NOT EXISTS texto_base SMALLINT;
-- Las normas procesadas antes con el metodo de 200 palabras se vuelven a leer completas
UPDATE normas SET texto_estado = NULL, texto_tsv = NULL WHERE texto_estado IS NOT NULL AND texto_base IS NULL;
CREATE INDEX IF NOT EXISTS idx_normas_texto_pend ON normas (fecha DESC) WHERE texto_estado IS NULL;

CREATE TABLE IF NOT EXISTS textos (
    tipo      CHAR(1)     NOT NULL,          -- N = norma, P = proyecto de ley
    doc_id    BIGINT      NOT NULL,          -- id en la tabla normas o proyectos_ley
    texto     TEXT        NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tipo, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_textos_busqueda ON textos USING GIN (to_tsvector('spanish', texto));
