-- Voltreo: cuentas de JUGADOR (autoservicio del portal público).
-- Idempotente, re-ejecutable. Ejecutar en Supabase SQL Editor.
-- Requiere haber ejecutado antes src/db_elo.sql (tabla players).

CREATE TABLE IF NOT EXISTS public.player_accounts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id       uuid NOT NULL REFERENCES public.clubs(id) ON DELETE CASCADE,
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    full_name     text NOT NULL,
    name          text NOT NULL DEFAULT '',
    surname       text NOT NULL DEFAULT '',
    phone         text NOT NULL DEFAULT '',
    -- DNI/NIE: identificación interna del club. NUNCA se muestra en el portal.
    dni           text NOT NULL DEFAULT '',
    -- Vínculo con la identidad ELO (tabla players). Puede ser NULL si falló
    -- la vinculación; se reintenta al entrar al perfil.
    player_id     uuid REFERENCES public.players(id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_player_accounts_club  ON public.player_accounts(club_id);
CREATE INDEX IF NOT EXISTS idx_player_accounts_email ON public.player_accounts(email);

ALTER TABLE public.player_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS player_accounts_service ON public.player_accounts;
CREATE POLICY player_accounts_service ON public.player_accounts
    FOR ALL USING (auth.role() = 'service_role')
              WITH CHECK (auth.role() = 'service_role');

GRANT ALL ON public.player_accounts TO service_role;
