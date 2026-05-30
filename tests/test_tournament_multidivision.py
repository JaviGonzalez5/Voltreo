"""
Tests del torneo MULTI-CATEGORÍA: un solo torneo con varias divisiones.

Verifica:
  · Cada división genera su propio cuadro (independiente).
  · El avance del cuadro no se cruza entre categorías.
  · El scheduler reparte todos los partidos sobre las MISMAS pistas sin solaparse.
  · Campeón por división.
"""
from datetime import date, time

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TournamentCourt, MatchRound, TMatchStatus,
)
from src.tournament_generator import generate_tournament_structure
from src.tournament_results import (
    register_result, tournament_champion, champions_by_division, results_summary,
)
from src.tournament_scheduler import schedule_tournament


def _pl(n): return TournamentPlayer(name=n, surname="")
def _pair(n, div): return TournamentPair(name=n, player_1=_pl(n + "1"), player_2=_pl(n + "2"), division=div)


def _multi_config(fmt=TournamentFormat.BRACKET):
    """Torneo con 2 divisiones: Masculino 1ª (4 parejas) y Femenino 1ª (4 parejas)."""
    masc = "masculino:1a"
    fem  = "femenino:1a"
    pairs = (
        [_pair(f"M{i}", masc) for i in range(4)] +
        [_pair(f"F{i}", fem)  for i in range(4)]
    )
    cfg = TournamentConfig(
        name="Open", start_date=date(2026, 6, 1), end_date=date(2026, 6, 7),
        divisions=[masc, fem],
        format=fmt, bracket_size=4,
        courts=[TournamentCourt(id="c1", name="Pista 1"), TournamentCourt(id="c2", name="Pista 2")],
        pairs=pairs,
        match_duration_minutes=60, rest_between_matches_min=15,
        day_start_time=time(9, 0), day_end_time=time(22, 0),
    )
    return generate_tournament_structure(cfg)


class TestMultiDivisionGeneration:

    def test_creates_one_draw_per_division(self):
        cfg = _multi_config()
        assert cfg.is_multi_division
        assert len(cfg.division_draws) == 2
        keys = {d.key for d in cfg.division_draws}
        assert keys == {"masculino:1a", "femenino:1a"}

    def test_each_division_has_own_matches(self):
        cfg = _multi_config()
        for d in cfg.division_draws:
            assert len(d.matches) > 0
            # Todos los partidos de la división están etiquetados con su clave
            assert all(m.division == d.key for m in d.matches)

    def test_union_matches_include_all_divisions(self):
        cfg = _multi_config()
        total = sum(len(d.matches) for d in cfg.division_draws)
        assert len(cfg.matches) == total

    def test_pairs_isolated_by_division(self):
        cfg = _multi_config()
        masc_draw = next(d for d in cfg.division_draws if d.key == "masculino:1a")
        # Solo parejas M en la división masculina
        names = {p.name for p in masc_draw.pairs}
        assert all(n.startswith("M") for n in names)


class TestMultiDivisionAdvancement:

    def test_winner_advances_within_own_division(self):
        cfg = _multi_config()
        # SF1 de masculino
        masc_sf1 = next(m for m in cfg.matches
                        if m.division == "masculino:1a"
                        and m.round == MatchRound.SEMIFINAL and m.match_number == 1)
        register_result(cfg, masc_sf1.id, masc_sf1.pair_1.id, "6-0 6-0")

        # La final masculina recibe al ganador; la femenina NO se toca
        masc_final = next(m for m in cfg.matches
                          if m.division == "masculino:1a" and m.round == MatchRound.FINAL)
        fem_final = next(m for m in cfg.matches
                         if m.division == "femenino:1a" and m.round == MatchRound.FINAL)
        assert masc_final.pair_1 is not None and masc_final.pair_1.id == masc_sf1.pair_1.id
        assert fem_final.pair_1 is None  # división femenina intacta

    def test_champion_per_division(self):
        cfg = _multi_config()
        # Completar SOLO la división masculina
        for i in (1, 2):
            sf = next(m for m in cfg.matches if m.division == "masculino:1a"
                      and m.round == MatchRound.SEMIFINAL and m.match_number == i)
            register_result(cfg, sf.id, sf.pair_1.id)
        masc_final = next(m for m in cfg.matches if m.division == "masculino:1a"
                          and m.round == MatchRound.FINAL)
        register_result(cfg, masc_final.id, masc_final.pair_1.id, "7-5 6-4")

        champs = champions_by_division(cfg)
        assert champs["masculino:1a"] is not None
        assert champs["femenino:1a"] is None  # femenina sin terminar


class TestMultiDivisionScheduling:

    def test_no_court_overlap_across_divisions(self):
        cfg = _multi_config()
        cfg = schedule_tournament(cfg)
        scheduled = [m for m in cfg.matches if m.status == TMatchStatus.SCHEDULED]
        assert len(scheduled) > 0
        # Ninguna pista tiene dos partidos solapados (de cualquier división)
        by_court = {}
        for m in scheduled:
            by_court.setdefault(m.court.id, []).append(m)
        for court_id, ms in by_court.items():
            ms.sort(key=lambda m: (m.match_date, m.start_time))
            for a, b in zip(ms, ms[1:]):
                if a.match_date == b.match_date:
                    assert a.end_time <= b.start_time, (
                        f"Solapamiento en {court_id}: {a.start_time}-{a.end_time} "
                        f"y {b.start_time}-{b.end_time}"
                    )

    def test_both_divisions_get_scheduled(self):
        cfg = _multi_config()
        cfg = schedule_tournament(cfg)
        masc = [m for m in cfg.matches if m.division == "masculino:1a"
                and m.status == TMatchStatus.SCHEDULED]
        fem = [m for m in cfg.matches if m.division == "femenino:1a"
               and m.status == TMatchStatus.SCHEDULED]
        assert len(masc) > 0
        assert len(fem) > 0


class TestBackwardCompatibility:

    def test_single_division_still_works(self):
        """Torneo de una sola categoría sigue funcionando como antes."""
        cfg = TournamentConfig(
            name="Single", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
            divisions=["masculino:1a"], format=TournamentFormat.BRACKET, bracket_size=4,
            courts=[TournamentCourt(id="c1", name="Pista 1")],
            pairs=[_pair(f"P{i}", "masculino:1a") for i in range(4)],
        )
        cfg = generate_tournament_structure(cfg)
        # Una sola división → no usa division_draws (camino legacy)
        assert not cfg.is_multi_division
        assert len(cfg.matches) > 0

    def test_no_divisions_legacy_path(self):
        cfg = TournamentConfig(
            name="Legacy", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
            format=TournamentFormat.BRACKET, bracket_size=4,
            courts=[TournamentCourt(id="c1", name="Pista 1")],
            pairs=[_pair(f"P{i}", None) for i in range(4)],
        )
        cfg = generate_tournament_structure(cfg)
        assert len(cfg.matches) > 0


class TestFinalPhaseSizing:
    """Fase final configurable tras los grupos."""

    def _groups_bracket(self, bracket_size, group_size, qualifiers, n_pairs):
        from src.tournament_models import TournamentConfig, TournamentFormat, TournamentCourt
        cfg = TournamentConfig(
            name="GB", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
            format=TournamentFormat.GROUPS_BRACKET,
            group_size=group_size, groups_qualifiers=qualifiers, bracket_size=bracket_size,
            courts=[TournamentCourt(id="c1", name="P1")],
            pairs=[_pair(f"P{i}", None) for i in range(n_pairs)],
        )
        return generate_tournament_structure(cfg)

    def test_solo_final_no_semifinals(self):
        cfg = self._groups_bracket(bracket_size=2, group_size=3, qualifiers=1, n_pairs=6)
        assert any(m.round == MatchRound.FINAL for m in cfg.matches)
        assert not any(m.round == MatchRound.SEMIFINAL for m in cfg.matches)

    def test_semis_plus_final(self):
        cfg = self._groups_bracket(bracket_size=4, group_size=4, qualifiers=2, n_pairs=8)
        assert len([m for m in cfg.matches if m.round == MatchRound.SEMIFINAL]) == 2
        assert len([m for m in cfg.matches if m.round == MatchRound.FINAL]) == 1

    def test_bracket_capped_by_qualifiers(self):
        # Pide cuadro de 8 pero solo hay 2 clasificados → se reduce a final (2)
        cfg = self._groups_bracket(bracket_size=8, group_size=3, qualifiers=1, n_pairs=6)
        assert not any(m.round == MatchRound.QUARTERFINAL for m in cfg.matches)
        assert any(m.round == MatchRound.FINAL for m in cfg.matches)
