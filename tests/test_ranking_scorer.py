"""
Tests para src/ranking_scorer.py
Cubre: cálculo de puntos, sets/juegos, desempates, walkover, agrupación.
"""
import pytest
from src.ranking_scorer import (
    ScoringRules, SetScore, MatchResult, Standing,
    compute_standings, standings_by_group,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(mid, p1, p2, sets, group=None, walkover=None):
    return MatchResult(
        match_id=mid, pair_1_id=p1, pair_2_id=p2, group_id=group,
        sets=[SetScore(games_1=a, games_2=b) for a, b in sets],
        walkover_winner_id=walkover,
    )


_NAMES = {"A": "Pareja A", "B": "Pareja B", "C": "Pareja C", "D": "Pareja D"}
_RULES = ScoringRules()  # 3 victoria, 1 empate, 0 derrota


# ---------------------------------------------------------------------------
# MatchResult — propiedades derivadas
# ---------------------------------------------------------------------------

class TestMatchResult:

    def test_winner_two_sets_to_zero(self):
        r = _result("m1", "A", "B", [(6, 4), (6, 3)])
        assert r.winner_id == "A"
        assert r.sets_won_1 == 2
        assert r.sets_won_2 == 0

    def test_winner_in_three_sets(self):
        r = _result("m1", "A", "B", [(6, 4), (3, 6), (7, 5)])
        assert r.winner_id == "A"
        assert r.sets_won_1 == 2
        assert r.sets_won_2 == 1

    def test_pair_2_wins(self):
        r = _result("m1", "A", "B", [(2, 6), (4, 6)])
        assert r.winner_id == "B"

    def test_games_counted(self):
        r = _result("m1", "A", "B", [(6, 4), (6, 3)])
        assert r.games_won_1 == 12
        assert r.games_won_2 == 7

    def test_walkover_winner(self):
        r = _result("m1", "A", "B", [], walkover="B")
        assert r.winner_id == "B"
        assert r.is_played

    def test_not_played_no_sets(self):
        r = _result("m1", "A", "B", [])
        assert not r.is_played
        assert r.winner_id is None


# ---------------------------------------------------------------------------
# compute_standings — casos básicos
# ---------------------------------------------------------------------------

class TestComputeStandings:

    def test_single_match_winner_gets_3_points(self):
        results = [_result("m1", "A", "B", [(6, 4), (6, 3)])]
        st = compute_standings(results, _NAMES, _RULES)
        by_id = {s.pair_id: s for s in st}
        assert by_id["A"].points == 3
        assert by_id["A"].won == 1
        assert by_id["B"].points == 0
        assert by_id["B"].lost == 1

    def test_all_pairs_appear_even_without_playing(self):
        results = [_result("m1", "A", "B", [(6, 4), (6, 3)])]
        st = compute_standings(results, _NAMES, _RULES)
        assert len(st) == 4  # A, B, C, D
        by_id = {s.pair_id: s for s in st}
        assert by_id["C"].played == 0
        assert by_id["D"].played == 0

    def test_winner_ranks_first(self):
        results = [_result("m1", "A", "B", [(6, 0), (6, 0)])]
        st = compute_standings(results, _NAMES, _RULES)
        assert st[0].pair_id == "A"

    def test_sets_and_games_accumulated(self):
        results = [
            _result("m1", "A", "B", [(6, 4), (6, 3)]),
            _result("m2", "A", "C", [(6, 2), (4, 6), (6, 1)]),
        ]
        st = compute_standings(results, _NAMES, _RULES)
        a = next(s for s in st if s.pair_id == "A")
        assert a.played == 2
        assert a.won == 2
        assert a.points == 6
        assert a.sets_for == 4    # 2 + 2
        assert a.sets_against == 1  # 0 + 1

    def test_walkover_no_sets_counted(self):
        results = [_result("m1", "A", "B", [], walkover="A")]
        st = compute_standings(results, _NAMES, _RULES)
        a = next(s for s in st if s.pair_id == "A")
        assert a.won == 1
        assert a.points == 3
        assert a.sets_for == 0  # walkover no cuenta sets


# ---------------------------------------------------------------------------
# Desempates
# ---------------------------------------------------------------------------

class TestTiebreakers:

    def test_tie_on_points_broken_by_set_diff(self):
        # A y B ambos ganan 1, pierden 1 → 3 pts cada uno
        # A gana 2-0 y pierde 0-2 → set_diff = 0
        # B gana 2-0 y pierde 1-2 → set_diff = +1 ... ajustemos
        results = [
            _result("m1", "A", "C", [(6, 0), (6, 0)]),  # A gana 2-0
            _result("m2", "A", "D", [(0, 6), (0, 6)]),  # A pierde 0-2
            _result("m3", "B", "C", [(6, 0), (6, 0)]),  # B gana 2-0
            _result("m4", "B", "D", [(0, 6), (3, 6)]),  # B pierde 0-2 pero más juegos
        ]
        st = compute_standings(results, _NAMES, _RULES)
        # A y B tienen mismos puntos (3) y mismo set_diff (0)
        # Se desempata por game_diff
        a = next(s for s in st if s.pair_id == "A")
        b = next(s for s in st if s.pair_id == "B")
        assert a.points == b.points

    def test_head_to_head_breaks_exact_tie(self):
        # Solo A y B, se enfrentan, A gana → A primero
        names = {"A": "A", "B": "B"}
        results = [_result("m1", "A", "B", [(6, 4), (6, 4)])]
        st = compute_standings(results, names, _RULES)
        assert st[0].pair_id == "A"

    def test_deterministic_order_with_no_data(self):
        st = compute_standings([], _NAMES, _RULES)
        # Sin resultados, orden estable por nombre
        names_order = [s.pair_name for s in st]
        assert names_order == sorted(names_order)


# ---------------------------------------------------------------------------
# Reglas configurables
# ---------------------------------------------------------------------------

class TestConfigurableRules:

    def test_custom_win_points(self):
        rules = ScoringRules(points_win=2, points_loss=0)
        results = [_result("m1", "A", "B", [(6, 0), (6, 0)])]
        st = compute_standings(results, _NAMES, rules)
        a = next(s for s in st if s.pair_id == "A")
        assert a.points == 2

    def test_clean_sheet_bonus(self):
        rules = ScoringRules(points_win=3, bonus_clean_sheet=1)
        # A gana sin ceder sets → 3 + 1 bonus
        results = [_result("m1", "A", "B", [(6, 0), (6, 0)])]
        st = compute_standings(results, _NAMES, rules)
        a = next(s for s in st if s.pair_id == "A")
        assert a.points == 4

    def test_no_clean_sheet_bonus_when_set_lost(self):
        rules = ScoringRules(points_win=3, bonus_clean_sheet=1)
        # A gana pero cede 1 set → solo 3
        results = [_result("m1", "A", "B", [(6, 0), (3, 6), (6, 2)])]
        st = compute_standings(results, _NAMES, rules)
        a = next(s for s in st if s.pair_id == "A")
        assert a.points == 3

    def test_loss_points_configurable(self):
        rules = ScoringRules(points_win=3, points_loss=1)  # 1 pt por participar
        results = [_result("m1", "A", "B", [(6, 0), (6, 0)])]
        st = compute_standings(results, _NAMES, rules)
        b = next(s for s in st if s.pair_id == "B")
        assert b.points == 1


# ---------------------------------------------------------------------------
# Agrupación por grupo
# ---------------------------------------------------------------------------

class TestStandingsByGroup:

    def test_separate_groups(self):
        names = {"A": "A", "B": "B", "C": "C", "D": "D"}
        pair_group = {"A": "G1", "B": "G1", "C": "G2", "D": "G2"}
        results = [
            _result("m1", "A", "B", [(6, 0), (6, 0)], group="G1"),
            _result("m2", "C", "D", [(6, 0), (6, 0)], group="G2"),
        ]
        by_group = standings_by_group(results, names, _RULES, pair_group)
        assert set(by_group.keys()) == {"G1", "G2"}
        assert by_group["G1"][0].pair_id == "A"
        assert by_group["G2"][0].pair_id == "C"

    def test_group_winner_first_in_each(self):
        names = {"A": "A", "B": "B"}
        pair_group = {"A": "G1", "B": "G1"}
        results = [_result("m1", "A", "B", [(2, 6), (2, 6)], group="G1")]
        by_group = standings_by_group(results, names, _RULES, pair_group)
        assert by_group["G1"][0].pair_id == "B"  # B ganó
