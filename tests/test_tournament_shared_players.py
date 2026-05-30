"""
Tests: un jugador que compite en varias categorías no puede tener dos
partidos simultáneos (ej. juega Masculino y Mixto).
"""
from datetime import date, time, datetime

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TournamentCourt, TMatchStatus, MatchRound,
)
from src.tournament_generator import generate_tournament_structure
from src.tournament_scheduler import schedule_tournament, _player_key, _match_player_keys


def _pl(name): return TournamentPlayer(name=name, surname="")


def _overlaps(m1, m2) -> bool:
    if m1.match_date != m2.match_date:
        return False
    s1 = datetime.combine(m1.match_date, m1.start_time)
    e1 = datetime.combine(m1.match_date, m1.end_time)
    s2 = datetime.combine(m2.match_date, m2.start_time)
    e2 = datetime.combine(m2.match_date, m2.end_time)
    return s1 < e2 and s2 < e1


class TestPlayerKey:

    def test_normalizes_accents_and_case(self):
        assert _player_key(_pl("García")) == _player_key(_pl("garcia"))
        assert _player_key(_pl("José")) == _player_key(_pl("jose"))

    def test_match_player_keys_four_players(self):
        p1 = TournamentPair(name="A", player_1=_pl("Ana"), player_2=_pl("Bea"))
        p2 = TournamentPair(name="B", player_1=_pl("Cleo"), player_2=_pl("Dora"))
        from src.tournament_models import TournamentMatch
        m = TournamentMatch(round=MatchRound.SEMIFINAL, match_number=1, pair_1=p1, pair_2=p2)
        keys = _match_player_keys(m)
        assert len(keys) == 4


class TestSharedPlayerNoSimultaneous:

    def test_player_in_two_categories_no_overlap(self):
        # "Carlos" juega en Masculino (con Diego) y en Mixto (con Marta)
        carlos_m = TournamentPair(name="Carlos/Diego",
                                  player_1=_pl("Carlos"), player_2=_pl("Diego"),
                                  division="masculino:1a")
        masc_pairs = [carlos_m] + [
            TournamentPair(name=f"M{i}", player_1=_pl(f"Hm{i}"), player_2=_pl(f"Im{i}"),
                           division="masculino:1a")
            for i in range(3)
        ]
        carlos_x = TournamentPair(name="Carlos/Marta",
                                  player_1=_pl("Carlos"), player_2=_pl("Marta"),
                                  division="mixto:1a")
        mix_pairs = [carlos_x] + [
            TournamentPair(name=f"X{i}", player_1=_pl(f"Hx{i}"), player_2=_pl(f"Ix{i}"),
                           division="mixto:1a")
            for i in range(3)
        ]

        cfg = TournamentConfig(
            name="Open", start_date=date(2026, 6, 1), end_date=date(2026, 6, 7),
            divisions=["masculino:1a", "mixto:1a"],
            format=TournamentFormat.BRACKET, bracket_size=4,
            courts=[TournamentCourt(id="c1", name="Pista 1"),
                    TournamentCourt(id="c2", name="Pista 2"),
                    TournamentCourt(id="c3", name="Pista 3")],
            pairs=masc_pairs + mix_pairs,
            match_duration_minutes=60, rest_between_matches_min=15,
            day_start_time=time(9, 0), day_end_time=time(22, 0),
        )
        cfg = generate_tournament_structure(cfg)
        cfg = schedule_tournament(cfg)

        # Todos los partidos en los que juega Carlos
        carlos_key = _player_key(_pl("Carlos"))
        carlos_matches = [
            m for m in cfg.matches
            if m.status == TMatchStatus.SCHEDULED
            and carlos_key in _match_player_keys(m)
        ]
        # Carlos juega en ambas categorías
        assert len(carlos_matches) >= 2
        divisions_played = {m.division for m in carlos_matches}
        assert "masculino:1a" in divisions_played
        assert "mixto:1a" in divisions_played

        # Ninguno de sus partidos se solapa con otro
        for i in range(len(carlos_matches)):
            for j in range(i + 1, len(carlos_matches)):
                assert not _overlaps(carlos_matches[i], carlos_matches[j]), (
                    f"Carlos tiene dos partidos simultáneos: "
                    f"{carlos_matches[i].match_date} {carlos_matches[i].start_time} "
                    f"y {carlos_matches[j].start_time}"
                )

    def test_rest_respected_between_player_matches(self):
        # Carlos juega dos partidos: deben respetar el descanso mínimo
        carlos_m = TournamentPair(name="Carlos/Diego",
                                  player_1=_pl("Carlos"), player_2=_pl("Diego"),
                                  division="masculino:1a")
        masc = [carlos_m] + [TournamentPair(name=f"M{i}", player_1=_pl(f"Hm{i}"),
                             player_2=_pl(f"Im{i}"), division="masculino:1a") for i in range(3)]
        carlos_x = TournamentPair(name="Carlos/Marta",
                                  player_1=_pl("Carlos"), player_2=_pl("Marta"),
                                  division="mixto:1a")
        mix = [carlos_x] + [TournamentPair(name=f"X{i}", player_1=_pl(f"Hx{i}"),
                            player_2=_pl(f"Ix{i}"), division="mixto:1a") for i in range(3)]

        cfg = TournamentConfig(
            name="Open", start_date=date(2026, 6, 1), end_date=date(2026, 6, 7),
            divisions=["masculino:1a", "mixto:1a"],
            format=TournamentFormat.BRACKET, bracket_size=4,
            courts=[TournamentCourt(id=f"c{i}", name=f"Pista {i}") for i in range(1, 5)],
            pairs=masc + mix,
            match_duration_minutes=60, rest_between_matches_min=30,
            day_start_time=time(9, 0), day_end_time=time(22, 0),
        )
        cfg = schedule_tournament(generate_tournament_structure(cfg))

        carlos_key = _player_key(_pl("Carlos"))
        cm = sorted(
            [m for m in cfg.matches if m.status == TMatchStatus.SCHEDULED
             and carlos_key in _match_player_keys(m)],
            key=lambda m: (m.match_date, m.start_time),
        )
        for a, b in zip(cm, cm[1:]):
            if a.match_date == b.match_date:
                gap = (datetime.combine(b.match_date, b.start_time)
                       - datetime.combine(a.match_date, a.end_time)).total_seconds() / 60
                assert gap >= 30, f"Descanso insuficiente: {gap} min"
