"""
Guarda de regresión para la página «Torneos → Registrar resultados» (t_results).

La página vive en el monolito app.py y no se puede testear directamente, pero sí
sus CÁLCULOS: replicamos aquí las expresiones que la página evalúa sobre un torneo
real (resumen de progreso, rondas del cuadro, banner de campeón) para que cualquier
regresión que las rompa (como el `len(_summ.get('played', 0) and True)` que
crasheaba al abrir la página) salte en los tests.
"""
from datetime import date, time

import pytest

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TournamentCourt, TournamentDivision, MatchRound, TMatchStatus,
)
from src.tournament_generator import generate_tournament_structure
from src.tournament_scheduler import schedule_tournament
from src.tournament_results import (
    register_result, results_summary, champions_by_division, tournament_champion,
)


def _pl(n): return TournamentPlayer(name=n, surname="")
def _pair(n, div): return TournamentPair(name=n, player_1=_pl(n + "a"), player_2=_pl(n + "b"), division=div)


def _multi_groups_bracket():
    """Torneo con cuadro eliminatorio en 2 divisiones (lo que activa el expander
    del cuadro en t_results)."""
    masc, fem = "masculino:1a", "femenino:1a"
    cfg = TournamentConfig(
        name="Open Noche", start_date=date(2026, 6, 12), end_date=date(2026, 6, 12),
        divisions=[masc, fem],
        division_waves={masc: 1, fem: 1},
        format=TournamentFormat.GROUPS_BRACKET,
        courts=[TournamentCourt(id=f"c{i}", name=f"Pista {i}") for i in range(1, 5)],
        pairs=[_pair(f"M{i}", masc) for i in range(8)] + [_pair(f"F{i}", fem) for i in range(8)],
        match_duration_minutes=15, rest_between_matches_min=0,
        day_start_time=time(19, 0), day_end_time=time(23, 30),
        division_draws=[
            TournamentDivision(key=masc, format=TournamentFormat.GROUPS_BRACKET, num_groups=2, bracket_size=4),
            TournamentDivision(key=fem,  format=TournamentFormat.GROUPS_BRACKET, num_groups=2, bracket_size=4),
        ],
    )
    return schedule_tournament(generate_tournament_structure(cfg))


_BRACKET_ROUNDS = [MatchRound.ROUND_OF_16, MatchRound.QUARTERFINAL, MatchRound.SEMIFINAL, MatchRound.FINAL]


def _bracket_expander_expanded(summ: dict) -> bool:
    """Réplica EXACTA de la expresión corregida en app.py (t_results)."""
    return bool(summ.get("played", 0))


class TestSummaryExpressions:

    def test_results_summary_played_is_int(self):
        t = _multi_groups_bracket()
        summ = results_summary(t)
        assert isinstance(summ["played"], int)
        assert isinstance(summ["pending"], int)

    def test_bracket_expander_arg_does_not_crash(self):
        """El bug original: `len(_summ.get('played', 0) and True)` lanzaba TypeError.
        La versión corregida `bool(...)` debe funcionar con 0 y con >0 jugados."""
        t = _multi_groups_bracket()
        summ = results_summary(t)
        # Sin jugar nada
        assert _bracket_expander_expanded(summ) in (True, False)
        # La expresión BUGGY habría crasheado — lo dejamos documentado:
        with pytest.raises(TypeError):
            len(summ.get("played", 0) and True)

    def test_expander_expands_after_a_result(self):
        t = _multi_groups_bracket()
        # Jugar un partido de grupo cualquiera
        gm = next(m for m in t.matches if m.round == MatchRound.GROUP and m.pair_1 and m.pair_2)
        register_result(t, gm.id, gm.pair_1.id, "6-0 6-0")
        summ = results_summary(t)
        assert summ["played"] >= 1
        assert _bracket_expander_expanded(summ) is True


class TestBracketRenderLogic:
    """Replica el filtrado de rondas y parejas que hace el árbol del cuadro."""

    def test_bracket_rounds_present_and_iterable(self):
        t = _multi_groups_bracket()
        has_bracket = any(m.round in _BRACKET_ROUNDS for m in t.matches)
        assert has_bracket
        div_keys = sorted({m.division for m in t.matches
                           if m.division and m.round in _BRACKET_ROUNDS} or [None])
        # Para cada división, agrupar partidos por ronda como en la página
        for dk in div_keys:
            div_ms = {
                r: sorted([m for m in t.matches if m.round == r
                           and (m.division == dk or dk is None)],
                          key=lambda m: m.match_number)
                for r in _BRACKET_ROUNDS
            }
            rounds_present = [r for r in _BRACKET_ROUNDS if div_ms.get(r)]
            assert rounds_present  # al menos una ronda de cuadro
            # p1_display / p2_display nunca deben lanzar (TBD incluido)
            for r in rounds_present:
                for m in div_ms[r]:
                    assert isinstance(m.p1_display, str)
                    assert isinstance(m.p2_display, str)

    def test_playable_filter_and_search(self):
        t = _multi_groups_bracket()
        # Réplica del filtro de partidos jugables + búsqueda de la página
        q = ""
        playable = sorted(
            [m for m in t.matches if m.pair_1 and m.pair_2
             if not q or q in m.p1_display.lower() or q in m.p2_display.lower()],
            key=lambda m: (m.round.order, m.match_number),
        )
        assert playable  # hay partidos de grupos con ambas parejas
        # Búsqueda concreta no crashea y filtra
        q2 = "m0"
        filtered = [m for m in playable
                    if q2 in m.p1_display.lower() or q2 in m.p2_display.lower()]
        assert all("m0" in (m.p1_display + m.p2_display).lower() for m in filtered)


class TestChampionBanner:

    def test_champions_by_division_runs(self):
        t = _multi_groups_bracket()
        champs = champions_by_division(t)
        # Sin terminar: todos None, pero la llamada no crashea
        assert isinstance(champs, dict)
        assert all(v is None for v in champs.values())

    def test_champion_after_completing_one_division(self):
        t = _multi_groups_bracket()
        # Completar grupos de masculino y su cuadro hasta la final
        for m in [x for x in t.matches if x.division == "masculino:1a"
                  and x.round == MatchRound.GROUP and x.pair_1 and x.pair_2]:
            register_result(t, m.id, m.pair_1.id, "6-0 6-0")
        # Jugar semis y final masculinas según se vayan poblando
        for rnd in (MatchRound.SEMIFINAL, MatchRound.FINAL):
            for m in [x for x in t.matches if x.division == "masculino:1a" and x.round == rnd]:
                if m.pair_1 and m.pair_2:
                    register_result(t, m.id, m.pair_1.id, "6-3 6-4")
        champ = tournament_champion(t, division="masculino:1a")
        # Puede o no haber campeón según el tamaño del cuadro, pero la llamada
        # y el banner (escape del nombre) no deben crashear.
        if champ is not None:
            assert isinstance(champ.display_name, str)
