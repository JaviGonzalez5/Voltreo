"""
Test E2E del flujo de ranking completo (sin Streamlit):
config → grupos → generar partidos → registrar resultados →
clasificación → serializar a DB → recargar → verificar persistencia.
"""
from datetime import date

from src.models import Player, Pair, Group, RankingPhase
from src.ranking_generator import generate_all_matches
from src.ranking_scorer import (
    ScoringRules, MatchResult, SetScore,
    compute_standings, standings_by_group,
)
from src.db_converters import phase_to_db, phase_from_db, schedule_result_to_db


def _pair(name: str) -> Pair:
    return Pair(
        name=name,
        player_1=Player(name=f"{name}1"),
        player_2=Player(name=f"{name}2"),
    )


def _build_phase() -> RankingPhase:
    g = Group(name="Grupo A", pairs=[_pair("A"), _pair("B"), _pair("C"), _pair("D")])
    return RankingPhase(
        name="Liga Test",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        groups=[g],
        scoring_rules=ScoringRules(points_win=3, points_loss=0),
    )


class TestRankingFullFlow:

    def test_full_flow_config_to_standings(self):
        phase = _build_phase()
        group = phase.groups[0]

        # 1. Generar partidos (round-robin: C(4,2)=6)
        matches = generate_all_matches(phase.groups)
        assert len(matches) == 6

        # 2. Registrar resultados — A gana todos, B segundo
        pairs = {p.name: p for p in group.pairs}
        results = []
        for m in matches:
            p1, p2 = m.pair_1, m.pair_2
            # A siempre gana
            if p1.name == "A" or p2.name == "A":
                winner = p1 if p1.name == "A" else p2
                loser  = p2 if p1.name == "A" else p1
                results.append(MatchResult(
                    match_id=m.id, pair_1_id=p1.id, pair_2_id=p2.id, group_id=m.group_id,
                    sets=[
                        SetScore(games_1=6 if winner is p1 else 0, games_2=0 if winner is p1 else 6),
                        SetScore(games_1=6 if winner is p1 else 0, games_2=0 if winner is p1 else 6),
                    ],
                ))
            else:
                # Entre B/C/D: gana el alfabéticamente menor
                winner_is_1 = p1.name < p2.name
                results.append(MatchResult(
                    match_id=m.id, pair_1_id=p1.id, pair_2_id=p2.id, group_id=m.group_id,
                    sets=[
                        SetScore(games_1=6 if winner_is_1 else 3, games_2=3 if winner_is_1 else 6),
                        SetScore(games_1=6 if winner_is_1 else 4, games_2=4 if winner_is_1 else 6),
                    ],
                ))
        phase.match_results = results

        # 3. Clasificación
        pair_names = {p.id: p.display_name for p in group.pairs}
        standings = compute_standings(results, pair_names, phase.scoring_rules)

        # A debe ser primero con 3 victorias (9 pts)
        assert standings[0].pair_name == pairs["A"].display_name
        assert standings[0].won == 3
        assert standings[0].points == 9

        # Todos jugaron 3 partidos
        for s in standings:
            assert s.played == 3

    def test_results_persist_through_db_round_trip(self):
        phase = _build_phase()
        matches = generate_all_matches(phase.groups)

        # Registrar 1 resultado
        m = matches[0]
        phase.match_results = [MatchResult(
            match_id=m.id, pair_1_id=m.pair_1.id, pair_2_id=m.pair_2.id,
            group_id=m.group_id,
            sets=[SetScore(games_1=6, games_2=2), SetScore(games_1=6, games_2=4)],
        )]

        # Serializar como hace la app
        payload = phase_to_db(phase, "club1", phase.id)
        row = {
            "id": phase.id, "name": phase.name,
            "start_date": "2026-06-01", "end_date": "2026-06-30",
            "config_json": payload["phase_config"],
            "groups_json": payload["groups_data"],
            "bookings_json": payload["bookings_data"],
            "matches_json": None,
        }

        # Recargar
        phase2, _ = phase_from_db(row)

        # Los resultados sobreviven
        assert len(phase2.match_results) == 1
        assert phase2.match_results[0].winner_id == m.pair_1.id
        assert phase2.scoring_rules.points_win == 3

    def test_scoring_rules_persist(self):
        phase = _build_phase()
        phase.scoring_rules = ScoringRules(points_win=2, points_draw=1, bonus_clean_sheet=1)

        payload = phase_to_db(phase, "club1", phase.id)
        row = {
            "id": phase.id, "name": phase.name,
            "start_date": "2026-06-01", "end_date": "2026-06-30",
            "config_json": payload["phase_config"],
            "groups_json": payload["groups_data"],
            "bookings_json": payload["bookings_data"],
            "matches_json": None,
        }
        phase2, _ = phase_from_db(row)
        assert phase2.scoring_rules.points_win == 2
        assert phase2.scoring_rules.bonus_clean_sheet == 1


class TestMultiTenantDataIsolation:
    """Simula el aislamiento entre clubes a nivel de serialización."""

    def test_phase_carries_correct_club_id(self):
        phase = _build_phase()
        payload_a = phase_to_db(phase, "clubA", None)
        payload_b = phase_to_db(phase, "clubB", None)
        assert payload_a["club_id"] == "clubA"
        assert payload_b["club_id"] == "clubB"

    def test_two_clubs_independent_results(self):
        """Resultados de club A no contaminan los de club B."""
        phase_a = _build_phase()
        phase_b = _build_phase()

        ma = generate_all_matches(phase_a.groups)[0]
        phase_a.match_results = [MatchResult(
            match_id=ma.id, pair_1_id=ma.pair_1.id, pair_2_id=ma.pair_2.id,
            sets=[SetScore(games_1=6, games_2=0), SetScore(games_1=6, games_2=0)],
        )]
        # Club B sin resultados
        assert len(phase_a.match_results) == 1
        assert len(phase_b.match_results) == 0
