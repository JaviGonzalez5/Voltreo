"""
Test-oráculo de la planilla de cruces.

Usa los DATOS REALES del Grupo 1.1 del Excel del club ("RESULTADOS RANKING FASE 3"),
verificados a mano, para garantizar que el cálculo (puntos 3/1/0, dif sets, dif
juegos y CLAS) coincide EXACTAMENTE con la planilla del cliente.
"""

from src.models import Pair, Player
from src.ranking_scorer import MatchResult, SetScore, ScoringRules
from src.cross_matrix import build_group_matrix

RULES = ScoringRules(points_win=3, points_loss=1, points_draw=0)


def _pair(pid, name):
    return Pair.model_construct(
        id=pid, name=name,
        player_1=Player.model_construct(id=pid + "a", name=name, surname=""),
        player_2=Player.model_construct(id=pid + "b", name="", surname=""),
        group_id="G1",
    )


def _mr(p1, p2, sets):
    return MatchResult(
        match_id=f"{p1}-{p2}", pair_1_id=p1, pair_2_id=p2, group_id="G1",
        sets=[SetScore(games_1=a, games_2=b) for a, b in sets],
    )


# Parejas en orden de siembra (1..6), igual que en el Excel del club
ENS, REY, LOP, ROD, ANO, BLA = "ens", "rey", "lop", "rod", "ano", "bla"
PAIRS = [
    _pair(ENS, "J. Enseñat- F. Monroy"),
    _pair(REY, "I. Rey- M. Amado"),
    _pair(LOP, "J. Lopez- T. Añon"),
    _pair(ROD, "C. Rodriguez- T. Herbera"),
    _pair(ANO, "T. Añon- A. Vidal"),
    _pair(BLA, "J. Blanco- M. Varela"),
]

# Partidos jugados (sets desde la perspectiva de pair_1)
RESULTS = [
    _mr(REY, ENS, [(7, 6), (5, 7), (6, 0)]),   # Rey gana 2-1
    _mr(ENS, ROD, [(6, 3), (7, 6)]),           # Enseñat gana 2-0
    _mr(ENS, BLA, [(1, 6), (6, 1), (6, 2)]),   # Enseñat gana 2-1
    _mr(REY, ROD, [(7, 6), (6, 3)]),           # Rey gana 2-0
    _mr(REY, BLA, [(6, 2), (6, 1)]),           # Rey gana 2-0
    _mr(ROD, BLA, [(7, 6), (6, 3)]),           # Rodriguez gana 2-0
]


def test_summary_matches_club_excel():
    m = build_group_matrix(PAIRS, RESULTS, RULES)
    rows = m["rows"]

    # (puntos, dif_sets, dif_juegos, clas) verificados contra la planilla
    assert (rows[REY]["points"], rows[REY]["set_diff"], rows[REY]["game_diff"], rows[REY]["clas"]) == (9, 5, 18, 1)
    assert (rows[ENS]["points"], rows[ENS]["set_diff"], rows[ENS]["game_diff"], rows[ENS]["clas"]) == (7, 2, 3, 2)
    assert (rows[ROD]["points"], rows[ROD]["set_diff"], rows[ROD]["game_diff"], rows[ROD]["clas"]) == (5, -2, -4, 3)
    assert (rows[BLA]["points"], rows[BLA]["set_diff"], rows[BLA]["game_diff"], rows[BLA]["clas"]) == (3, -5, -17, 4)

    # Parejas sin jugar: 0 puntos, al final (CLAS 5 y 6 por orden de siembra)
    assert rows[LOP]["points"] == 0 and rows[ANO]["points"] == 0
    assert {rows[LOP]["clas"], rows[ANO]["clas"]} == {5, 6}
    assert rows[LOP]["clas"] == 5  # Lopez (siembra 3) por delante de Añon (siembra 5)


def test_played_won_lost_counts():
    m = build_group_matrix(PAIRS, RESULTS, RULES)
    rows = m["rows"]
    assert (rows[ENS]["played"], rows[ENS]["won"], rows[ENS]["lost"]) == (3, 2, 1)
    assert (rows[REY]["played"], rows[REY]["won"], rows[REY]["lost"]) == (3, 3, 0)
    assert (rows[BLA]["played"], rows[BLA]["won"], rows[BLA]["lost"]) == (3, 0, 3)


def test_cell_detail_oriented_and_points():
    m = build_group_matrix(PAIRS, RESULTS, RULES)
    cells = m["cells"]

    # Rey (fila) vs Enseñat: 7-6 / 5-7 / 6-0, gana 2 sets, 3 puntos
    c = cells[(REY, ENS)]
    assert c["sets"] == [(7, 6), (5, 7), (6, 0)]
    assert c["sets_won"] == 2 and c["pts"] == 3

    # Espejo: Enseñat (fila) vs Rey, juegos invertidos, 1 set, 1 punto (derrota)
    c2 = cells[(ENS, REY)]
    assert c2["sets"] == [(6, 7), (7, 5), (0, 6)]
    assert c2["sets_won"] == 1 and c2["pts"] == 1


def test_unplayed_pair_has_no_cells():
    m = build_group_matrix(PAIRS, RESULTS, RULES)
    # Lopez no jugó: no aparece en ninguna celda
    assert not any(LOP in k for k in m["cells"])
