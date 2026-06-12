"""Tests del mapeo Syltek→Voltreo (build_results_from_round)."""

from src.models import Group, Pair, Player
from src.syltek_connector import parse_round_results
from src.syltek_sync import build_results_from_round, _norm
from tests.test_syltek_results_parser import GRUPO1_HTML


def _pair(name: str, gid: str) -> Pair:
    return Pair.model_construct(
        id=f"id-{name}", name=name,
        player_1=Player.model_construct(id="p1", name=name, surname=""),
        player_2=Player.model_construct(id="p2", name="", surname=""),
        group_id=gid,
    )


def _voltreo_groups_grupo1():
    names = [
        "J. Enseñat- F. Monroy", "C. Angeriz- G. Lendoiro", "I. Rey- M. Amado",
        "J. Blanco- M. Varela", "I. Rocha- I. Ortiz", "J. Lopez- T. Añon",
    ]
    g = Group.model_construct(id="G1", name="Nivel 1 — Grupo 1",
                              pairs=[_pair(n, "G1") for n in names])
    return [g]


def test_norm():
    assert _norm("J. Enseñat- F. Monroy") == "j enseñat- f monroy"
    assert _norm("  A.  B   ") == "a b"


def test_build_results_basic():
    parsed = parse_round_results(GRUPO1_HTML)
    groups = _voltreo_groups_grupo1()
    results, unmatched = build_results_from_round(parsed, groups)

    assert unmatched == []
    assert len(results) == 4  # 4 partidos jugados en Grupo 1

    by_id = {r.match_id: r for r in results}
    # Enseñat vs Angeriz (reserva 263662): 6-4 / 1-6 / 6-4 desde Enseñat
    r = by_id["263662"]
    assert r.pair_1_id == "id-J. Enseñat- F. Monroy"
    assert r.pair_2_id == "id-C. Angeriz- G. Lendoiro"
    assert [(s.games_1, s.games_2) for s in r.sets] == [(6, 4), (1, 6), (6, 4)]
    assert r.group_id == "G1"


def test_orientation_matches_winner():
    parsed = parse_round_results(GRUPO1_HTML)
    results, _ = build_results_from_round(parsed, _voltreo_groups_grupo1())
    by_id = {r.match_id: r for r in results}
    # 263662: Enseñat gana 2 sets a 1 → pair_1 (Enseñat) es el ganador
    r = by_id["263662"]
    assert r.sets_won_1 == 2 and r.sets_won_2 == 1
    assert r.winner_id == r.pair_1_id


def test_unmatched_reported():
    parsed = parse_round_results(GRUPO1_HTML)
    # Grupos Voltreo a los que les falta una pareja → sus partidos no casan
    g = Group.model_construct(id="G1", name="G1", pairs=[
        _pair("J. Enseñat- F. Monroy", "G1"),
        _pair("C. Angeriz- G. Lendoiro", "G1"),
    ])
    results, unmatched = build_results_from_round(parsed, [g])
    # Solo casa Enseñat vs Angeriz; el resto de jugados quedan sin casar
    assert len(results) == 1
    assert any("no encontrada" in u for u in unmatched)
