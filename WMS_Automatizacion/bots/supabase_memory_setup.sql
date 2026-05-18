-- ============================================================
-- Egakat Ops Bot — Memoria persistente en Supabase
-- Ejecutar en: Supabase > SQL Editor
-- Proyecto recomendado: el que ya usas para n8n/infraestructura
-- ============================================================

-- Tabla principal de historial de chat
CREATE TABLE IF NOT EXISTS egakat_ops_chat_memory (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT        NOT NULL,   -- chat_id de Telegram
    message     JSONB       NOT NULL,   -- contenido del mensaje (role + content)
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsqueda rápida por sesión
CREATE INDEX IF NOT EXISTS idx_egakat_ops_chat_memory_session
    ON egakat_ops_chat_memory (session_id);

-- Índice por fecha (útil para limpiezas futuras)
CREATE INDEX IF NOT EXISTS idx_egakat_ops_chat_memory_created
    ON egakat_ops_chat_memory (created_at);

-- ── Política RLS (opcional pero recomendada) ─────────────────
-- Si el proyecto tiene RLS habilitado, agregar política permisiva
-- para el service_role que usa n8n:
-- ALTER TABLE egakat_ops_chat_memory ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "service_role_all" ON egakat_ops_chat_memory
--     FOR ALL USING (auth.role() = 'service_role');

-- ── Limpieza automática (opcional) ──────────────────────────
-- Eliminar mensajes con más de 30 días (mantiene la tabla liviana)
-- Ejecutar manualmente o via pg_cron si lo tienes habilitado:
-- DELETE FROM egakat_ops_chat_memory
--     WHERE created_at < NOW() - INTERVAL '30 days';

-- ── Verificación ─────────────────────────────────────────────
SELECT 'Tabla creada OK' AS status,
       schemaname, tablename
FROM pg_tables
WHERE tablename = 'egakat_ops_chat_memory';
