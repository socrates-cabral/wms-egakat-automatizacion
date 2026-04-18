-- Crypto Bot — tablas Supabase
-- Ejecutar en Supabase SQL Editor una sola vez

-- Estado grid (una fila por par)
CREATE TABLE IF NOT EXISTS crypto_grid_state (
    par         TEXT PRIMARY KEY,
    estado      JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Historial de operaciones (append-only)
CREATE TABLE IF NOT EXISTS crypto_operaciones (
    id          BIGSERIAL PRIMARY KEY,
    par         TEXT NOT NULL,
    tipo        TEXT NOT NULL,          -- 'BUY' | 'SELL'
    precio      NUMERIC NOT NULL,
    qty         NUMERIC NOT NULL,
    pnl         NUMERIC,               -- solo en SELL
    order_id    TEXT,
    timestamp   TIMESTAMPTZ NOT NULL
);

-- Índice para queries por par + fecha
CREATE INDEX IF NOT EXISTS idx_crypto_op_par_ts ON crypto_operaciones (par, timestamp DESC);

-- RLS desactivado (tabla privada, acceso solo via service key)
ALTER TABLE crypto_grid_state  DISABLE ROW LEVEL SECURITY;
ALTER TABLE crypto_operaciones DISABLE ROW LEVEL SECURITY;
