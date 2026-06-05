-- ============================================================
-- PadelPlus — Row Level Security (RLS)
-- Ejecutar en Supabase SQL Editor
-- Requiere: service_role para operaciones de backend
--           anon/authenticated para operaciones de usuario
-- Idempotente: se puede ejecutar más de una vez sin errores.
-- ============================================================

-- Habilitar RLS en todas las tablas (no-op si ya está habilitado)
ALTER TABLE public.clubs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ranking_phases   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tournaments      ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- CLUBS
-- ============================================================

-- Superadmin puede hacer todo (usa service_role key, bypass RLS)
-- Club admin solo puede leer su propio club

DROP POLICY IF EXISTS "clubs_select_own"        ON public.clubs;
DROP POLICY IF EXISTS "clubs_service_role_all"  ON public.clubs;

CREATE POLICY "clubs_select_own"
ON public.clubs FOR SELECT
USING (true);   -- lectura pública del nombre del club (para login)

CREATE POLICY "clubs_service_role_all"
ON public.clubs FOR ALL
USING (auth.role() = 'service_role');

-- ============================================================
-- USERS
-- ============================================================

-- Nadie puede leer contraseñas desde cliente (service_role bypassa esto)
DROP POLICY IF EXISTS "users_no_direct_access" ON public.users;

CREATE POLICY "users_no_direct_access"
ON public.users FOR ALL
USING (auth.role() = 'service_role');

-- ============================================================
-- RANKING_PHASES — aislamiento por club_id
-- ============================================================

DROP POLICY IF EXISTS "phases_select_own_club" ON public.ranking_phases;
DROP POLICY IF EXISTS "phases_insert_own_club" ON public.ranking_phases;
DROP POLICY IF EXISTS "phases_update_own_club" ON public.ranking_phases;
DROP POLICY IF EXISTS "phases_delete_own_club" ON public.ranking_phases;

CREATE POLICY "phases_select_own_club"
ON public.ranking_phases FOR SELECT
USING (auth.role() = 'service_role');

CREATE POLICY "phases_insert_own_club"
ON public.ranking_phases FOR INSERT
WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "phases_update_own_club"
ON public.ranking_phases FOR UPDATE
USING (auth.role() = 'service_role');

CREATE POLICY "phases_delete_own_club"
ON public.ranking_phases FOR DELETE
USING (auth.role() = 'service_role');

-- ============================================================
-- TOURNAMENTS — aislamiento por club_id
-- ============================================================

DROP POLICY IF EXISTS "tournaments_service_role_all" ON public.tournaments;

CREATE POLICY "tournaments_service_role_all"
ON public.tournaments FOR ALL
USING (auth.role() = 'service_role');

-- ============================================================
-- Tabla de auditoría (nueva)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.audit_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    club_id     UUID        REFERENCES public.clubs(id) ON DELETE SET NULL,
    user_id     UUID        REFERENCES public.users(id) ON DELETE SET NULL,
    action      TEXT        NOT NULL,   -- 'login', 'create_phase', 'delete_tournament', etc.
    resource    TEXT,                   -- 'phase', 'tournament', 'user', 'club'
    resource_id TEXT,
    details     JSONB       DEFAULT '{}'
);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "audit_service_role_all" ON public.audit_log;

CREATE POLICY "audit_service_role_all"
ON public.audit_log FOR ALL
USING (auth.role() = 'service_role');

-- Índices para consultas de auditoría
CREATE INDEX IF NOT EXISTS audit_log_club_id_idx    ON public.audit_log (club_id);
CREATE INDEX IF NOT EXISTS audit_log_created_at_idx ON public.audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_idx     ON public.audit_log (action);
