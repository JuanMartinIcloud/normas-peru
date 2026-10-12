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
