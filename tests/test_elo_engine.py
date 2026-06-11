"""Tests del motor ELO."""
from src.elo_engine import (
    DEFAULT_ELO, ELO_FLOOR, K_FACTOR,
    expected_score, compute_match_deltas, seed_order, assign_seed_numbers,
)


def test_expected_score_equal_ratings_returns_half():
    assert abs(expected_score(1200, 1200) - 0.5) < 0.001


def test_expected_score_higher_rating_wins_more_often():
    e = expected_score(1400, 1200)
    assert 0.7 < e < 0.85  # ~76%


def test_expected_score_symmetry():
    assert abs(expected_score(1300, 1500) + expected_score(1500, 1300) - 1.0) < 0.001


def test_compute_match_deltas_winner_gains_loser_loses():
    elos = {"a1": 1200, "a2": 1200, "b1": 1200, "b2": 1200}
    deltas = compute_match_deltas(
        ("a1", "a2"), ("b1", "b2"), elos, winner_pair="A",
    )
    assert len(deltas) == 4
    by_id = {d.player_id: d for d in deltas}
    # Ganadores suben (~16 con todos iguales)
    assert by_id["a1"].delta > 0
    assert by_id["a2"].delta > 0
    # Perdedores bajan (mismo valor absoluto)
    assert by_id["b1"].delta < 0
    assert by_id["b2"].delta < 0
    # Conservación: suma de deltas = 0
    assert sum(d.delta for d in deltas) == 0


def test_compute_match_deltas_winner_gains_more_when_upsets_favorite():
    elos = {"a1": 1100, "a2": 1100, "b1": 1500, "b2": 1500}
    # El equipo débil (A) gana al fuerte (B)
    deltas_upset = compute_match_deltas(
        ("a1", "a2"), ("b1", "b2"), elos, winner_pair="A",
    )
    # El equipo fuerte gana al débil (resultado esperado)
    deltas_expected = compute_match_deltas(
        ("a1", "a2"), ("b1", "b2"), elos, winner_pair="B",
    )
    # En el upset, A sube mucho más que en el resultado esperado
    a1_upset = next(d for d in deltas_upset if d.player_id == "a1")
    b1_expected = next(d for d in deltas_expected if d.player_id == "b1")
    assert a1_upset.delta > b1_expected.delta


def test_compute_match_deltas_missing_player_uses_default():
    elos = {"a1": 1300}  # solo uno conocido
    deltas = compute_match_deltas(
        ("a1", "a2"), ("b1", "b2"), elos, winner_pair="A",
    )
    by_id = {d.player_id: d for d in deltas}
    assert by_id["a2"].elo_before == DEFAULT_ELO
    assert by_id["b1"].elo_before == DEFAULT_ELO


def test_compute_match_deltas_respects_elo_floor():
    elos = {"a1": 805, "a2": 805, "b1": 1800, "b2": 1800}
    deltas = compute_match_deltas(
        ("a1", "a2"), ("b1", "b2"), elos, winner_pair="B",
    )
    # A pierde mucho pero no debe bajar de ELO_FLOOR
    a1_delta = next(d for d in deltas if d.player_id == "a1")
    assert a1_delta.elo_after >= ELO_FLOOR


def test_compute_match_deltas_invalid_winner_raises():
    import pytest
    with pytest.raises(ValueError, match="winner_pair"):
        compute_match_deltas(("a1", "a2"), ("b1", "b2"), {}, winner_pair="X")


def test_seed_order_sorts_by_pair_elo_average():
    from types import SimpleNamespace
    pairs = [
        SimpleNamespace(id="weak",   player_1=SimpleNamespace(id="w1", name="W1"),
                                      player_2=SimpleNamespace(id="w2", name="W2")),
        SimpleNamespace(id="strong", player_1=SimpleNamespace(id="s1", name="S1"),
                                      player_2=SimpleNamespace(id="s2", name="S2")),
        SimpleNamespace(id="medium", player_1=SimpleNamespace(id="m1", name="M1"),
                                      player_2=SimpleNamespace(id="m2", name="M2")),
    ]
    elos = {"w1": 1000, "w2": 1000, "s1": 1600, "s2": 1500, "m1": 1300, "m2": 1300}
    ordered = seed_order(pairs, elos)
    assert [p.id for p in ordered] == ["strong", "medium", "weak"]


def test_assign_seed_numbers_returns_1_for_best():
    from types import SimpleNamespace
    pairs = [
        SimpleNamespace(id="x", player_1=SimpleNamespace(id="x1", name="X1"),
                                 player_2=SimpleNamespace(id="x2", name="X2")),
        SimpleNamespace(id="y", player_1=SimpleNamespace(id="y1", name="Y1"),
                                 player_2=SimpleNamespace(id="y2", name="Y2")),
    ]
    elos = {"x1": 1500, "x2": 1500, "y1": 1100, "y2": 1100}
    seeds = assign_seed_numbers(pairs, elos)
    assert seeds["x"] == 1  # cabeza de serie 1 (más ELO)
    assert seeds["y"] == 2
