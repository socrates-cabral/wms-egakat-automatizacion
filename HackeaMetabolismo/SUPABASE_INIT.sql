-- SUPABASE_INIT.sql
-- Ejecuta este script en Supabase dashboard: SQL Editor
-- Crear todas las tablas necesarias para Hackea tu Metabolismo

CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    nombre          TEXT    NOT NULL,
    email           TEXT    UNIQUE,
    fecha_nac       TEXT    NOT NULL,
    sexo            TEXT    CHECK(sexo IN ('M','F')) NOT NULL,
    altura_cm       REAL    NOT NULL,
    objetivo        TEXT    DEFAULT 'perder_grasa',
    nivel_actividad TEXT    DEFAULT 'moderado',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mediciones (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha       TEXT    NOT NULL,
    peso_kg     REAL,
    cintura_cm  REAL,
    cadera_cm   REAL,
    cuello_cm   REAL,
    notas       TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS objetivos (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    kcal_objetivo   REAL    NOT NULL,
    proteina_g      REAL    NOT NULL,
    cho_g           REAL    NOT NULL,
    grasa_g         REAL    NOT NULL,
    deficit_kcal    REAL    DEFAULT 0,
    tdee            REAL,
    tmb             REAL,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registros_alimentos (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    momento         TEXT    DEFAULT 'almuerzo',
    alimento        TEXT    NOT NULL,
    porcion_g       REAL,
    kcal            REAL    NOT NULL,
    proteina_g      REAL    DEFAULT 0,
    cho_g           REAL    DEFAULT 0,
    grasa_g         REAL    DEFAULT 0,
    fibra_g         REAL    DEFAULT 0,
    fuente          TEXT    DEFAULT 'manual',
    es_estimado     INTEGER DEFAULT 0,
    confianza_ia    TEXT,
    notas           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registros_ejercicio (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    tipo            TEXT    NOT NULL,
    categoria       TEXT    DEFAULT 'fuerza',
    duracion_min    INTEGER DEFAULT 0,
    kcal_quemadas   REAL    DEFAULT 0,
    intensidad      TEXT    DEFAULT 'moderada',
    notas           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS registros_sueno (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    horas           REAL    NOT NULL,
    calidad         TEXT    DEFAULT 'buena',
    hora_acostarse  TEXT,
    hora_despertar  TEXT,
    notas           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Crear índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_alimentos_fecha  ON registros_alimentos(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ejercicio_fecha  ON registros_ejercicio(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_sueno_fecha      ON registros_sueno(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_mediciones_fecha ON mediciones(usuario_id, fecha);

-- Habilitar RLS (Row Level Security) - opcional pero recomendado
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE mediciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE objetivos ENABLE ROW LEVEL SECURITY;
ALTER TABLE registros_alimentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE registros_ejercicio ENABLE ROW LEVEL SECURITY;
ALTER TABLE registros_sueno ENABLE ROW LEVEL SECURITY;
