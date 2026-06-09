-- ============================================================
-- Ranking Padelplus — Schema PostgreSQL (Supabase)
-- Ejecutar en el SQL Editor de Supabase (una sola vez)
-- ============================================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ============================================================
-- 1. Clubs
-- ============================================================
CREATE TABLE IF NOT EXISTS clubs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    slug        TEXT        UNIQUE NOT NULL,   -- identificador URL-friendly p.ej. "padelplus-madrid"
    settings    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE clubs
ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}';

-- ============================================================
-- 2. Usuarios (auth propio con bcrypt, sin Supabase Auth)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id        UUID        REFERENCES clubs(id) ON DELETE CASCADE,
    -- club_id = NULL  →  superadmin (ve todos los clubs)
    username       TEXT        UNIQUE NOT NULL,
    password_hash  TEXT        NOT NULL,
    role           TEXT        NOT NULL CHECK (role IN ('superadmin', 'club_admin')),
    display_name   TEXT        DEFAULT '',
    email          TEXT        DEFAULT '',
    is_active      BOOLEAN     DEFAULT true,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_club ON users(club_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================
-- 3. Fases de ranking
--    Los datos complejos (grupos, parejas, pistas, partidos)
--    se guardan como JSONB para no necesitar 10 tablas en el MVP.
--    Se pueden normalizar más adelante si se necesita reporting.
-- ============================================================
-- IMPORTANTE: los nombres de columna deben coincidir EXACTAMENTE con los que
-- usa src/db.py (config_json / groups_json / bookings_json / matches_json).
-- Si no coinciden, PostgREST rechaza el upsert con "column not found" y CADA
-- guardado/carga de ranking falla.
CREATE TABLE IF NOT EXISTS ranking_phases (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id         UUID        NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    start_date      DATE        NOT NULL,
    end_date        DATE        NOT NULL,
    -- Configuración de la fase (RankingPhase sin groups/bookings)
    config_json     JSONB       NOT NULL DEFAULT '{}',
    -- Grupos y parejas importados (list[Group])
    groups_json     JSONB       NOT NULL DEFAULT '[]',
    -- Reservas Syltek importadas (list[Booking])
    bookings_json   JSONB       NOT NULL DEFAULT '[]',
    -- Resultado del calendario generado (ScheduleResult | null)
    matches_json    JSONB,
    is_active       BOOLEAN     DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Migración auto-reparadora (idempotente) ──────────────────────────────────
-- Tablas creadas con el esquema antiguo tenían columnas phase_config / groups_data
-- / bookings_data / schedule_result. Las renombramos a los nombres que el código
-- espera. Si ya están renombradas, no hace nada. Ejecutable cuantas veces se quiera.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='ranking_phases' AND column_name='phase_config') THEN
        ALTER TABLE public.ranking_phases RENAME COLUMN phase_config TO config_json;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='ranking_phases' AND column_name='groups_data') THEN
        ALTER TABLE public.ranking_phases RENAME COLUMN groups_data TO groups_json;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='ranking_phases' AND column_name='bookings_data') THEN
        ALTER TABLE public.ranking_phases RENAME COLUMN bookings_data TO bookings_json;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='ranking_phases' AND column_name='schedule_result') THEN
        ALTER TABLE public.ranking_phases RENAME COLUMN schedule_result TO matches_json;
    END IF;
END $$;

-- Garantizar que existen las columnas con el nombre correcto (instalaciones mixtas).
ALTER TABLE public.ranking_phases ADD COLUMN IF NOT EXISTS config_json   JSONB NOT NULL DEFAULT '{}';
ALTER TABLE public.ranking_phases ADD COLUMN IF NOT EXISTS groups_json   JSONB NOT NULL DEFAULT '[]';
ALTER TABLE public.ranking_phases ADD COLUMN IF NOT EXISTS bookings_json JSONB NOT NULL DEFAULT '[]';
ALTER TABLE public.ranking_phases ADD COLUMN IF NOT EXISTS matches_json  JSONB;
-- matches_json puede ser NULL (una fase nueva todavía no tiene calendario).
-- Si una instalación lo creó como NOT NULL, el INSERT de una fase nueva fallaba
-- con "null value in column matches_json ... violates not-null constraint".
ALTER TABLE public.ranking_phases ALTER COLUMN matches_json DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_phases_club    ON ranking_phases(club_id);
CREATE INDEX IF NOT EXISTS idx_phases_active  ON ranking_phases(club_id, is_active);

-- ============================================================
-- 4. Torneos
-- ============================================================
CREATE TABLE IF NOT EXISTS tournaments (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id          UUID        NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    name             TEXT        NOT NULL,
    start_date       DATE        NOT NULL,
    end_date         DATE        NOT NULL,
    -- TournamentConfig completo serializado
    tournament_data  JSONB       NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tournaments_club ON tournaments(club_id);

-- ============================================================
-- 5. Función helper para updated_at automático
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_phases_updated_at
    BEFORE UPDATE ON ranking_phases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER trg_tournaments_updated_at
    BEFORE UPDATE ON tournaments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- DATOS INICIALES — Superadmin
-- Cambia 'superadmin' y el hash antes de ejecutar en producción.
-- Hash generado con: python -c "import bcrypt; print(bcrypt.hashpw(b'admin1234', bcrypt.gensalt()).decode())"
-- ============================================================

-- Insertar sólo si no existe
INSERT INTO users (club_id, username, password_hash, role, display_name)
SELECT NULL, 'superadmin',
    -- hash de 'admin1234' — CAMBIA esto en producción
    '$2b$12$placeholder_change_me_before_prod',
    'superadmin', 'Super Admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'superadmin');
