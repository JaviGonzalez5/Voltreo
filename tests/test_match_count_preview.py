"""
Tests de la previsión de partidos por grupo/cuadro (t_generate).

`preview_match_counts` debe devolver EXACTAMENTE los mismos números que el
generador real produce, para que la previsión mostrada al admin no engañe.
"""
from datetime import date, time

import pytest

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TournamentCourt, TournamentDivision, MatchRound,
)
from src.tournament_generator import (
    generate_tournament_structure, group_sizes_for, preview_match_counts,
)


def _pl(n): return TournamentPlayer(name=n, surname="")
def _pair(n, d): return TournamentPair(name=n, player_1=_pl(n + "a"), player_2=_pl(n + "b"), division=d)


def _real_counts(n_pairs, num_groups, final_phase, third):
    div = "masculino:3a"
    fmt = TournamentFormat.GROUPS if final_phase == 0 else TournamentFormat.GROUPS_BRACKET
    cfg = TournamentConfig(
        name="t", start_date=date(2026, 6, 12), end_date=date(2026, 6, 12),
        divisions=[div], format=fmt, third_place_match=third,
        courts=[TournamentCourt(id="c", name="P")],
        pairs=[_pair(f"P{i}", div) for i in range(n_pairs)],
        group_size=4, bracket_size=max(2, final_phase),
        day_start_time=time(19, 0), day_end_time=time(23, 0),
        division_draws=[TournamentDivision(
            key=div, format=fmt, num_groups=num_groups, bracket_size=max(2, final_phase),
            group_size=4, groups_qualifiers=2, third_place_match=third)],
    )
    g = generate_tournament_structure(cfg)
    grp = sum(1 for m in g.matches if m.round == MatchRound.GROUP)
    fin = sum(1 for m in g.matches if m.round != MatchRound.GROUP)
    return grp, fin


# (n_pairs, num_groups, final_phase, third_place)
_CASES = [
    (12, 3, 8, False), (12, 3, 8, True),
    (8, 2, 4, False),  (8, 2, 4, True),
    (16, 4, 8, False), (16, 4, 16, True),
    (6, 2, 2, False),  (9, 3, 4, True),
    (20, 5, 8, False), (12, 3, 0, False),
    (16, 4, 4, True),  (24, 6, 8, True),
]


@pytest.mark.parametrize("n_pairs,num_groups,final_phase,third", _CASES)
def test_preview_matches_generator(n_pairs, num_groups, final_phase, third):
    pv = preview_match_counts(group_sizes_for(n_pairs, num_groups), final_phase, third_place=third)
    real_g, real_f = _real_counts(n_pairs, num_groups, final_phase, third)
    assert pv["group_matches"] == real_g, "partidos de grupos no coinciden con el generador"
    assert pv["final_matches"] == real_f, "partidos de fase final no coinciden con el generador"
    assert pv["total"] == real_g + real_f


class TestExpectedTotalMatches:

    def _multi(self, draws_spec):
        from src.tournament_models import TournamentConfig, TournamentDivision
        divs = [k for k, _ng, _bs in draws_spec]
        pairs = []
        draws = []
        for k, ng, bs in draws_spec:
            np_ = ng * 4  # 4 parejas por grupo
            dpairs = [_pair(f"{k[:3]}{k[-1]}_{i}", k) for i in range(np_)]
            pairs += dpairs
            draws.append(TournamentDivision(
                key=k, format=TournamentFormat.GROUPS_BRACKET, num_groups=ng,
                bracket_size=bs, group_size=4, groups_qualifiers=2, pairs=dpairs))
        cfg = TournamentConfig(
            name="t", start_date=date(2026, 6, 12), end_date=date(2026, 6, 12),
            divisions=divs, format=TournamentFormat.GROUPS_BRACKET,
            courts=[TournamentCourt(id="c", name="P")], pairs=pairs,
            day_start_time=time(19, 0), day_end_time=time(2, 0),
            division_draws=draws)
        return generate_tournament_structure(cfg)

    def test_expected_equals_generated_multi_division(self):
        from src.tournament_generator import expected_total_matches
        cfg = self._multi([("masculino:3a", 3, 4), ("femenino:3a", 2, 4), ("mixto:3a", 3, 4)])
        assert expected_total_matches(cfg) == len(cfg.matches)

    def test_returns_none_without_division_draws(self):
        from src.tournament_models import TournamentConfig
        from src.tournament_generator import expected_total_matches
        cfg = TournamentConfig(
            name="t", start_date=date(2026, 6, 12), end_date=date(2026, 6, 12),
            divisions=[], format=TournamentFormat.GROUPS_BRACKET,
            courts=[TournamentCourt(id="c", name="P")], pairs=[])
        assert expected_total_matches(cfg) is None


class TestGroupSizes:

    def test_even_split(self):
        assert group_sizes_for(12, 3) == [4, 4, 4]

    def test_uneven_split_extra_first(self):
        assert group_sizes_for(10, 3) == [4, 3, 3]

    def test_single_group(self):
        assert group_sizes_for(5, 1) == [5]


class TestPreviewBasics:

    def test_round_robin_per_group(self):
        # grupo de 4 → C(4,2)=6 partidos
        pv = preview_match_counts([4, 4], 0)
        assert pv["per_group"] == [6, 6]
        assert pv["group_matches"] == 12
        assert pv["final_matches"] == 0   # liguilla

    def test_solo_final(self):
        pv = preview_match_counts([3, 3], 2)
        assert pv["effective_bracket"] == 2
        assert pv["final_matches"] == 1

    def test_bracket_capped_by_qualifiers(self):
        # 2 grupos de 4 → 4 clasificados → cuadro pedido 8 se recorta a 4
        pv = preview_match_counts([4, 4], 8)
        assert pv["effective_bracket"] == 4
        assert pv["final_matches"] == 3   # 2 semis + 1 final

    def test_third_place_only_for_bracket_of_four(self):
        # cuadro 4 + 3er puesto → 2 semis + final + 3er = 4
        assert preview_match_counts([4, 4], 4, third_place=True)["final_matches"] == 4
        # cuadro 8 + 3er puesto → el generador NO añade 3er puesto → 7
        assert preview_match_counts([4, 4, 4, 4], 8, third_place=True)["final_matches"] == 7
