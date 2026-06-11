-- Voltreo: sistema ELO de jugadores con DOBLE contexto (ranking / torneos).
-- Idempotente, re-ejecutable. Ejecutar en Supabase SQL Editor.

-- ============================================================================
-- Tabla players: identidad estable del jugador por club + 2 ratings
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.players (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id      uuid NOT NULL REFERENCES public.clubs(id) ON DELETE CASCADE,
    full_name    text NOT NULL,
    name_key     text NOT NULL,          -- normalizado (lowercase, sin acentos)
    email        text DEFAULT '',
    phone        text DEFAULT '',
    -- ELO separado por contexto
    elo_ranking     integer NOT NULL DEFAULT 1200,
    elo_tournament  integer NOT NULL DEFAULT 1200,
    -- Estadísticas separadas por contexto
    matches_played_ranking     integer NOT NULL DEFAULT 0,
    matches_won_ranking        integer NOT NULL DEFAULT 0,
    matches_played_tournament  integer NOT NULL DEFAULT 0,
    matches_won_tournament     integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (club_id, name_key)
);

-- Migración desde el esquema antiguo de un solo ELO (si existiera)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='players' AND column_name='elo') THEN
        ALTER TABLE public.players RENAME COLUMN elo TO elo_tournament_old;
        UPDATE public.players SET elo_tournament = elo_tournament_old;
        ALTER TABLE public.players DROP COLUMN elo_tournament_old;
    END IF;
END $$;

ALTER TABLE public.players ADD COLUMN IF NOT EXISTS elo_ranking    integer NOT NULL DEFAULT 1200;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS elo_tournament integer NOT NULL DEFAULT 1200;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS matches_played_ranking    integer NOT NULL DEFAULT 0;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS matches_won_ranking       integer NOT NULL DEFAULT 0;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS matches_played_tournament integer NOT NULL DEFAULT 0;
ALTER TABLE public.players ADD COLUMN IF NOT EXISTS matches_won_tournament    integer NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_players_club ON public.players(club_id);
CREATE INDEX IF NOT EXISTS idx_players_club_elo_r ON public.players(club_id, elo_ranking DESC);
CREATE INDEX IF NOT EXISTS idx_players_club_elo_t ON public.players(club_id, elo_tournament DESC);

-- ============================================================================
-- Tabla elo_history: histórico de cambios, separable por contexto
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.elo_history (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id       uuid NOT NULL REFERENCES public.clubs(id) ON DELETE CASCADE,
    player_id     uuid NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    source_type   text NOT NULL CHECK (source_type IN ('tournament_match', 'ranking_match', 'manual')),
    source_id     text,              -- match_id: clave de idempotencia
    tournament_name text DEFAULT '', -- nombre del torneo o de la fase de ranking
    elo_before    integer NOT NULL,
    elo_after     integer NOT NULL,
    delta         integer NOT NULL,
    opponent_names text DEFAULT '',
    result        text DEFAULT '',
    played_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_elo_history_player_ctx
    ON public.elo_history(player_id, source_type, played_at DESC);
CREATE INDEX IF NOT EXISTS idx_elo_history_source
    ON public.elo_history(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_elo_history_club
    ON public.elo_history(club_id, played_at DESC);

-- ============================================================================
-- RLS (solo service_role) + permisos
-- ============================================================================
ALTER TABLE public.players     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.elo_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS players_service ON public.players;
CREATE POLICY players_service ON public.players
    FOR ALL USING (auth.role() = 'service_role')
              WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS elo_history_service ON public.elo_history;
CREATE POLICY elo_history_service ON public.elo_history
    FOR ALL USING (auth.role() = 'service_role')
              WITH CHECK (auth.role() = 'service_role');

GRANT ALL ON public.players     TO service_role;
GRANT ALL ON public.elo_history TO service_role;
