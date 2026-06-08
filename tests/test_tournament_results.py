"""
Tests para src/tournament_results.py
Cubre: registro de resultado, avance automático del cuadro,
       perdedor de SF → 3er puesto, borrado/recalculo, campeón.
"""
import pytest
from datetime import date

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    MatchRound, TMatchStatus,
)
from src.tournament_generator import generate_tournament_structure
from src.tournament_results import (
    register_result, clear_result, recompute_bracket,
    tournament_champion, results_summary,
)


def _player(n): return TournamentPlayer(name=n, surname="")
def _pair(n):   return TournamentPair(name=n, player_1=_player(f"{n}1"), player_2=_player(f"{n}2"))


def _bracket_config(n_pairs=4, third_place=False) -> TournamentConfig:
    cfg = TournamentConfig(
        name="Cup",
        start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
        format=TournamentFormat.BRACKET,
        bracket_size=n_pairs,
        third_place_match=third_place,
        pairs=[_pair(chr(65 + i)) for i in range(n_pairs)],  # A, B, C, D...
    )
    return generate_tournament_structure(cfg)


def _match(cfg, rnd, num):
    return next(m for m in cfg.matches if m.round == rnd and m.match_number == num)


# ---------------------------------------------------------------------------
# Registro básico
# ---------------------------------------------------------------------------

class TestRegisterResult:

    def test_register_sets_winner_and_score(self):
        cfg = _bracket_config(4)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        register_result(cfg, sf1.id, sf1.pair_1.id, "6-4 6-3")
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        assert sf1.winner_id == sf1.pair_1.id
        assert sf1.score == "6-4 6-3"
        assert sf1.is_played

    def test_invalid_winner_raises(self):
        cfg = _bracket_config(4)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        with pytest.raises(ValueError):
            register_result(cfg, sf1.id, "not-a-real-pair-id")

    def test_unknown_match_raises(self):
        cfg = _bracket_config(4)
        with pytest.raises(ValueError):
            register_result(cfg, "nope", "x")


# ---------------------------------------------------------------------------
# Avance automático del cuadro (4 parejas: 2 SF → 1 Final)
# ---------------------------------------------------------------------------

class TestBracketAdvancement4:

    def test_sf_winners_advance_to_final(self):
        cfg = _bracket_config(4)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        sf2 = _match(cfg, MatchRound.SEMIFINAL, 2)
        w1 = sf1.pair_1
        w2 = sf2.pair_1
        register_result(cfg, sf1.id, w1.id, "6-0 6-0")
        register_result(cfg, sf2.id, w2.id, "6-1 6-1")

        final = _match(cfg, MatchRound.FINAL, 1)
        # SF1 (impar) → pair_1, SF2 (par) → pair_2
        assert final.pair_1 is not None and final.pair_1.id == w1.id
        assert final.pair_2 is not None and final.pair_2.id == w2.id

    def test_champion_after_final(self):
        cfg = _bracket_config(4)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        sf2 = _match(cfg, MatchRound.SEMIFINAL, 2)
        register_result(cfg, sf1.id, sf1.pair_1.id)
        register_result(cfg, sf2.id, sf2.pair_1.id)
        final = _match(cfg, MatchRound.FINAL, 1)
        champ_to_be = final.pair_1
        register_result(cfg, final.id, champ_to_be.id, "7-5 6-4")
        champ = tournament_champion(cfg)
        assert champ is not None and champ.id == champ_to_be.id

    def test_no_champion_before_final(self):
        cfg = _bracket_config(4)
        assert tournament_champion(cfg) is None


# ---------------------------------------------------------------------------
# Avance con 8 parejas (QF → SF → Final)
# ---------------------------------------------------------------------------

class TestBracketAdvancement8:

    def test_qf_winners_fill_semifinals(self):
        cfg = _bracket_config(8)
        qfs = [_match(cfg, MatchRound.QUARTERFINAL, i) for i in range(1, 5)]
        winners = []
        for qf in qfs:
            register_result(cfg, qf.id, qf.pair_1.id)
            winners.append(qf.pair_1)

        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        sf2 = _match(cfg, MatchRound.SEMIFINAL, 2)
        # QF1→SF1.p1, QF2→SF1.p2, QF3→SF2.p1, QF4→SF2.p2
        assert sf1.pair_1.id == winners[0].id
        assert sf1.pair_2.id == winners[1].id
        assert sf2.pair_1.id == winners[2].id
        assert sf2.pair_2.id == winners[3].id

    def test_full_8_tournament_to_champion(self):
        cfg = _bracket_config(8)
        for i in range(1, 5):
            qf = _match(cfg, MatchRound.QUARTERFINAL, i)
            register_result(cfg, qf.id, qf.pair_1.id)
        for i in range(1, 3):
            sf = _match(cfg, MatchRound.SEMIFINAL, i)
            register_result(cfg, sf.id, sf.pair_1.id)
        final = _match(cfg, MatchRound.FINAL, 1)
        register_result(cfg, final.id, final.pair_1.id)
        assert tournament_champion(cfg) is not None


# ---------------------------------------------------------------------------
# Tercer puesto
# ---------------------------------------------------------------------------

class TestThirdPlace:

    def test_sf_losers_go_to_third_place(self):
        cfg = _bracket_config(4, third_place=True)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        sf2 = _match(cfg, MatchRound.SEMIFINAL, 2)
        loser1 = sf1.pair_2  # gana pair_1, pierde pair_2
        loser2 = sf2.pair_2
        register_result(cfg, sf1.id, sf1.pair_1.id)
        register_result(cfg, sf2.id, sf2.pair_1.id)

        tp = _match(cfg, MatchRound.THIRD_PLACE, 1)
        assert tp.pair_1 is not None and tp.pair_1.id == loser1.id
        assert tp.pair_2 is not None and tp.pair_2.id == loser2.id


# ---------------------------------------------------------------------------
# Borrado y recálculo
# ---------------------------------------------------------------------------

class TestClearAndRecompute:

    def test_clear_result_removes_downstream(self):
        cfg = _bracket_config(4)
        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        sf2 = _match(cfg, MatchRound.SEMIFINAL, 2)
        register_result(cfg, sf1.id, sf1.pair_1.id)
        register_result(cfg, sf2.id, sf2.pair_1.id)
        final = _match(cfg, MatchRound.FINAL, 1)
        assert final.pair_1 is not None

        # Borrar SF1 → la final pierde su pair_1
        clear_result(cfg, sf1.id)
        final = _match(cfg, MatchRound.FINAL, 1)
        assert final.pair_1 is None
        # SF2 winner sigue en la final (pair_2)
        assert final.pair_2 is not None

    def test_recompute_idempotent(self):
        cfg = _bracket_config(8)
        for i in range(1, 5):
            qf = _match(cfg, MatchRound.QUARTERFINAL, i)
            register_result(cfg, qf.id, qf.pair_1.id)
        sf1_before = _match(cfg, MatchRound.SEMIFINAL, 1).pair_1.id
        recompute_bracket(cfg)
        recompute_bracket(cfg)
        sf1_after = _match(cfg, MatchRound.SEMIFINAL, 1).pair_1.id
        assert sf1_before == sf1_after


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

class TestResultsSummary:

    def test_summary_counts(self):
        cfg = _bracket_config(4)
        s0 = results_summary(cfg)
        # Solo las 2 SF tienen ambas parejas al inicio (final es TBD)
        assert s0["played"] == 0
        assert s0["pending"] == 2

        sf1 = _match(cfg, MatchRound.SEMIFINAL, 1)
        register_result(cfg, sf1.id, sf1.pair_1.id)
        s1 = results_summary(cfg)
        assert s1["played"] == 1

    def test_champion_in_summary(self):
        cfg = _bracket_config(4)
        for i in (1, 2):
            sf = _match(cfg, MatchRound.SEMIFINAL, i)
            register_result(cfg, sf.id, sf.pair_1.id)
        final = _match(cfg, MatchRound.FINAL, 1)
        register_result(cfg, final.id, final.pair_1.id)
        s = results_summary(cfg)
        assert s["champion"] is not None


# ---------------------------------------------------------------------------
# Clasificación de la fase de grupos
# ---------------------------------------------------------------------------

from src.tournament_results import group_standings, _parse_score, GroupStanding


class TestParseScore:

    def test_two_sets(self):
        assert _parse_score("6-4 6-3") == (2, 0, 12, 7)

    def test_split_sets_with_commas(self):
        # 1 set cada uno, juegos sumados
        assert _parse_score("6-4, 3-6, 10-8") == (2, 1, 19, 18)

    def test_empty_and_garbage(self):
        assert _parse_score("") is None
        assert _parse_score("   ") is None
        assert _parse_score("walkover") is None


def _groups_config() -> TournamentConfig:
    cfg = TournamentConfig(
        name="Liga",
        start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
        format=TournamentFormat.GROUPS,
        group_size=4,
        pairs=[_pair(chr(65 + i)) for i in range(4)],  # A B C D → 1 grupo, 6 partidos
    )
    return generate_tournament_structure(cfg)


class TestGroupStandings:

    def test_all_pairs_listed_even_without_results(self):
        cfg = _groups_config()
        st = group_standings(cfg)
        assert len(st) == 1
        table = next(iter(st.values()))
        assert len(table) == 4
        assert all(s.played == 0 and s.points == 0 for s in table)

    def test_win_gives_three_points_and_orders_top(self):
        cfg = _groups_config()
        gid = cfg.groups[0].id
        gms = [m for m in cfg.matches if m.round == MatchRound.GROUP]
        # Pareja A gana todos sus partidos del grupo
        a_id = cfg.pairs[0].id
        for m in gms:
            if m.pair_1.id == a_id:
                register_result(cfg, m.id, a_id, "6-1 6-1")
            elif m.pair_2.id == a_id:
                register_result(cfg, m.id, a_id, "1-6 1-6")
        table = group_standings(cfg)[gid]
        top = table[0]
        assert top.pair_id == a_id
        assert top.won == 3 and top.lost == 0
        assert top.points == 9
        assert top.set_diff == 6  # 6 sets a favor, 0 en contra

    def test_division_filter(self):
        cfg = _groups_config()
        # Sin división → devuelve el grupo; con división inexistente → grupo vacío
        assert group_standings(cfg, division="no-existe") == {}
