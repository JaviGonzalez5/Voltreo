-- ============================================================================
-- Voltreo — Tabla de inscripciones públicas de torneos
-- ============================================================================
-- Motivo: la inscripción pública (?join) escribía re-guardando TODO el JSONB
-- del torneo (read-modify-write) → carrera / lost-update con el admin y con
-- otras inscripciones simultáneas. Esta tabla permite INSERT atómico por fila.
--
-- Flujo:
--   · Público (?join)  → INSERT de una fila aquí (status 'pending').
--   · Admin (t_pairs)  → "drena" las filas al JSONB del torneo y las borra.
--
-- Idempotente: se puede ejecutar varias veces sin error.
-- Ejecutar en: Supabase → SQL Editor.
-- ============================================================================

create table if not exists public.tournament_registrations (
    id            uuid primary key default gen_random_uuid(),
    tournament_id uuid not null,
    club_id       uuid,
    data          jsonb not null default '{}'::jsonb,
    status        text  not null default 'pending',
    created_at    timestamptz not null default now()
);

create index if not exists idx_tournament_registrations_tid
    on public.tournament_registrations (tournament_id);

-- Row Level Security: solo la app (service_role) accede. Nadie más.
alter table public.tournament_registrations enable row level security;

drop policy if exists tr_service_role_all on public.tournament_registrations;
create policy tr_service_role_all
    on public.tournament_registrations
    for all
    to service_role
    using (true)
    with check (true);
