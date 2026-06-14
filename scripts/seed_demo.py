"""
Genera un club demo completo en Supabase para presentaciones de Voltreo.

Crea: 1 club, 1 usuario club_admin, 12 jugadores (con identidad ELO), una fase
de ranking activa con clasificación poblada, y un torneo con grupos + cuadro
generados (resultados de la fase de grupos rellenos) más inscripciones pendientes.

Usa la MISMA capa de datos que la app (src/db.py, src/db_elo.py, generadores)
en vez de SQL crudo, para respetar toda la lógica de negocio.

Idempotente: si el club demo ya existe, lo borra (cascade) y lo recrea limpio.

Credenciales: NO hay secretos en el archivo. Las credenciales de Supabase se
leen del entorno (SUPABASE_URL / SUPABASE_KEY), igual que la app. La contraseña
del admin demo se lee de DEMO_ADMIN_PASSWORD; si no está, se genera una aleatoria
y se imprime al terminar.

Uso:
    # Windows PowerShell
    $env:SUPABASE_URL="https://xxxx.supabase.co"
    $env:SUPABASE_KEY="<service_role key>"
    python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import date
from pathlib import Path
from random import Random

# Permitir `import src...` al ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import hash_password
from src.db import get_db, is_db_configured
from src import db_elo
from src.models import (
    Group, Pair, Player, RankingPhase,
)
from src.ranking_scorer import MatchResult, ScoringRules, SetScore
from src.ranking_generator import generate_round_robin
from src.tournament_models import (
    TournamentConfig, TournamentCourt, TournamentFormat,
    TournamentPair, TournamentPlayer, MatchRound,
)
from src.tournament_generator import generate_tournament_structure


# ---------------------------------------------------------------------------
# Constantes del club demo
# ---------------------------------------------------------------------------

DEMO_CLUB_NAME = "Club Demo Voltreo"
DEMO_CLUB_SLUG = "club-demo-voltreo"
DEMO_ADMIN_USERNAME = "demo_admin"

# 12 jugadores realistas. (nombre, apellido)
DEMO_PLAYERS: list[tuple[str, str]] = [
    ("Carlos", "García"),    ("Javier", "Martínez"),
    ("Miguel", "Fernández"), ("David", "López"),
    ("Alejandro", "Sánchez"),("Daniel", "Pérez"),
    ("Pablo", "Gómez"),      ("Sergio", "Ruiz"),
    ("Adrián", "Díaz"),      ("Álvaro", "Moreno"),
    ("Rubén", "Jiménez"),    ("Marcos", "Romero"),
]

RANKING_PHASE_NAME = "Liga de Primavera 2026"
TOURNAMENT_NAME = "Torneo Apertura Voltreo 2026"

rng = Random(42)  # resultados deterministas y reproducibles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email(name: str, surname: str) -> str:
    base = f"{name}.{surname}".lower()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), (" ", "")]:
        base = base.replace(a, b)
    return f"{base}@clubdemo.voltreo"


def _phone(i: int) -> str:
    return f"+34 6{i:02d} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def _fabricate_result(pair_1_id: str, pair_2_id: str, group_id: str, match_id: str):
    """Inventa un resultado realista. Devuelve (MatchResult, winner_pair, score)."""
    a_wins = rng.random() < 0.5
    loser_games_1 = rng.randint(2, 4)
    loser_games_2 = rng.randint(2, 4)
    if a_wins:
        sets = [SetScore(games_1=6, games_2=loser_games_1),
                SetScore(games_1=6, games_2=loser_games_2)]
        score = f"6-{loser_games_1} 6-{loser_games_2}"
        winner_pair = "A"
    else:
        sets = [SetScore(games_1=loser_games_1, games_2=6),
                SetScore(games_1=loser_games_2, games_2=6)]
        score = f"{loser_games_1}-6 {loser_games_2}-6"
        winner_pair = "B"
    result = MatchResult(
        match_id=match_id, pair_1_id=pair_1_id, pair_2_id=pair_2_id,
        group_id=group_id, sets=sets,
    )
    return result, winner_pair, score


# ---------------------------------------------------------------------------
# Pasos
# ---------------------------------------------------------------------------

def wipe_existing(db) -> bool:
    """Borra el club demo si existe (incluidas inscripciones sin cascade FK)."""
    existing = db.get_club_by_slug(DEMO_CLUB_SLUG)
    if not existing:
        return False
    club_id = existing["id"]
    # tournament_registrations no tiene FK cascade → limpiar a mano primero.
    for t in db.list_tournaments(club_id):
        reg_ids = [r["id"] for r in db.list_registrations(t["id"])]
        if reg_ids:
            db.delete_registrations(reg_ids)
    # delete_club cascada: users, ranking_phases, tournaments, players,
    # elo_history, player_accounts.
    db.delete_club(club_id)
    return True


def create_club_and_admin(db, admin_password: str) -> tuple[str, str]:
    club = db.create_club(DEMO_CLUB_NAME, DEMO_CLUB_SLUG)
    club_id = club["id"]
    db.create_user(
        username=DEMO_ADMIN_USERNAME,
        password_hash=hash_password(admin_password),
        role="club_admin",
        club_id=club_id,
        display_name="Admin Club Demo",
        email="admin@clubdemo.voltreo",
    )
    return club_id, DEMO_ADMIN_USERNAME


def create_players(club_id: str) -> list[dict]:
    """Crea los 12 jugadores en la tabla players (identidad ELO).
    Devuelve dicts: {id, name, surname, full_name, email, phone}."""
    out: list[dict] = []
    for i, (name, surname) in enumerate(DEMO_PLAYERS, start=1):
        full = f"{name} {surname}"
        email = _email(name, surname)
        phone = _phone(i)
        row = db_elo.get_or_create_player(club_id, full, email=email, phone=phone)
        if not row:
            raise RuntimeError(f"No se pudo crear el jugador {full}")
        out.append({
            "id": row["id"], "name": name, "surname": surname,
            "full_name": full, "email": email, "phone": phone,
        })
    return out


def build_ranking(db, club_id: str, players: list[dict]) -> dict:
    """Crea una fase de ranking activa con clasificación poblada + ELO."""
    # 6 parejas (12 jugadores), un grupo round-robin.
    model_players = [
        Player(id=p["id"], name=p["name"], surname=p["surname"],
               email=p["email"], phone=p["phone"])
        for p in players
    ]
    pairs: list[Pair] = []
    for a in range(0, len(model_players), 2):
        p1, p2 = model_players[a], model_players[a + 1]
        pairs.append(Pair(
            name=f"{p1.surname} / {p2.surname}",
            player_1=p1, player_2=p2,
        ))
    group = Group(name="Grupo A", pairs=pairs)

    # Round-robin con la lógica real de la app.
    matches = generate_round_robin(group)

    results: list[MatchResult] = []
    elo_recorded = 0
    for m in matches:
        result, winner_pair, score = _fabricate_result(
            m.pair_1.id, m.pair_2.id, group.id, m.id,
        )
        results.append(result)
        # ELO contexto "ranking": 4 jugadores reales del club.
        db_elo.record_match_result(
            club_id=club_id,
            context="ranking",
            source_id=m.id,
            event_name=RANKING_PHASE_NAME,
            pair_a_player_ids=(m.pair_1.player_1.id, m.pair_1.player_2.id),
            pair_a_names=(m.pair_1.player_1.full_name, m.pair_1.player_2.full_name),
            pair_b_player_ids=(m.pair_2.player_1.id, m.pair_2.player_2.id),
            pair_b_names=(m.pair_2.player_1.full_name, m.pair_2.player_2.full_name),
            winner_pair=winner_pair,
            score=score,
        )
        elo_recorded += 1

    phase = RankingPhase(
        name=RANKING_PHASE_NAME,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 30),
        groups=[group],
        scoring_rules=ScoringRules(),
        match_results=results,
    )

    from src.db_converters import phase_to_db
    payload = phase_to_db(phase, club_id)
    db.upsert_phase(**payload, schedule_result=None)

    return {"pairs": len(pairs), "matches": len(matches), "elo": elo_recorded}


def build_tournament(db, club_id: str, players: list[dict]) -> dict:
    """Crea un torneo GRUPOS+CUADRO con resultados de grupos rellenos."""
    t_players = [
        TournamentPlayer(id=p["id"], name=p["name"], surname=p["surname"],
                         email=p["email"], phone=p["phone"])
        for p in players
    ]
    t_pairs: list[TournamentPair] = []
    for a in range(0, len(t_players), 2):
        p1, p2 = t_players[a], t_players[a + 1]
        t_pairs.append(TournamentPair(
            name=f"{p1.surname} / {p2.surname}",
            player_1=p1, player_2=p2, seed=(a // 2) + 1,
        ))

    config = TournamentConfig(
        name=TOURNAMENT_NAME,
        start_date=date(2026, 6, 20),
        end_date=date(2026, 6, 21),
        location=DEMO_CLUB_NAME,
        courts=[TournamentCourt(name=f"Pista {i}") for i in range(1, 4)],
        pairs=t_pairs,
        format=TournamentFormat.GROUPS_BRACKET,
        group_size=3,
        groups_qualifiers=2,
        bracket_size=4,
        third_place_match=True,
        registration_open=True,
    )
    config = generate_tournament_structure(config)

    # Rellenar SOLO los resultados de la fase de grupos. El cuadro queda generado
    # con rivales "Por determinar" (avanzar el cuadro es lógica fuera de alcance).
    group_played = 0
    for m in config.matches:
        if m.round != MatchRound.GROUP:
            continue
        if not (m.pair_1 and m.pair_2):
            continue
        a_wins = rng.random() < 0.5
        winner = m.pair_1 if a_wins else m.pair_2
        lg1, lg2 = rng.randint(2, 4), rng.randint(2, 4)
        m.winner_id = winner.id
        m.score = (f"6-{lg1} 6-{lg2}" if a_wins else f"{lg1}-6 {lg2}-6")
        group_played += 1

    from src.db_converters import tournament_to_db
    payload = tournament_to_db(config, club_id)
    db.upsert_tournament(**payload)

    # Inscripciones públicas pendientes (bandeja del admin no vacía).
    pending = [
        {"player1_name": "Lucía", "player1_surname1": "Navarro",
         "player2_name": "Marta", "player2_surname1": "Ortega",
         "pair_name": "L. Navarro – M. Ortega", "status": "pending"},
        {"player1_name": "Iván", "player1_surname1": "Torres",
         "player2_name": "Hugo", "player2_surname1": "Castro",
         "pair_name": "I. Torres – H. Castro", "status": "pending"},
    ]
    regs = 0
    for data in pending:
        if db.add_registration(config.id, club_id, data) is not None:
            regs += 1

    return {"pairs": len(t_pairs), "group_results": group_played,
            "registrations": regs, "tournament_id": config.id}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not is_db_configured():
        print("ERROR: faltan SUPABASE_URL y SUPABASE_KEY en el entorno.")
        print("Configúralas antes de ejecutar (igual que la app).")
        return 1

    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD") or secrets.token_urlsafe(9)
    generated_pw = "DEMO_ADMIN_PASSWORD" not in os.environ

    db = get_db()

    print("→ Limpiando club demo previo (si existe)...")
    wiped = wipe_existing(db)
    print(f"  {'borrado y recreado' if wiped else 'no existía, creando de cero'}")

    print("→ Creando club y usuario admin...")
    club_id, username = create_club_and_admin(db, admin_password)

    print("→ Creando 12 jugadores (identidad ELO)...")
    players = create_players(club_id)

    print("→ Generando ranking con clasificación + ELO...")
    rk = build_ranking(db, club_id, players)

    print("→ Generando torneo (grupos + cuadro)...")
    tt = build_tournament(db, club_id, players)

    # ---- Resumen ----
    print("\n" + "=" * 56)
    print("  DATOS DEMO CREADOS")
    print("=" * 56)
    print(f"  Club            : {DEMO_CLUB_NAME}  (slug: {DEMO_CLUB_SLUG})")
    print(f"  Jugadores       : {len(players)} (con ELO)")
    print(f"  Ranking         : '{RANKING_PHASE_NAME}' (activo)")
    print(f"                    {rk['pairs']} parejas, {rk['matches']} partidos jugados")
    print(f"                    {rk['elo']} partidos registrados en ELO")
    print(f"  Torneo          : '{TOURNAMENT_NAME}'")
    print(f"                    {tt['pairs']} parejas, {tt['group_results']} resultados de grupo")
    print(f"                    {tt['registrations']} inscripciones pendientes")
    print("-" * 56)
    print("  CÓMO ENTRAR")
    print(f"  Usuario   : {username}")
    if generated_pw:
        print(f"  Contraseña: {admin_password}   (generada — guárdala)")
    else:
        print("  Contraseña: (la de $DEMO_ADMIN_PASSWORD)")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
