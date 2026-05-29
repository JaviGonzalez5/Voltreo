"""
Tests de Pista Fija (PF) en el scheduler.

Garantiza que cuando una pareja tiene pista fija (preferred_weekday + preferred_time)
y ambas parejas están disponibles ese día/hora, el partido se asigna SIEMPRE en
esa franja, sin que lo desplacen penalizaciones (late_hour) ni la aleatoriedad.
"""
from datetime import date, time

from src.models import (
    Player, Pair, Group, Court, RankingPhase, BalanceWeights, MatchStatus,
)
from src.scheduler import Scheduler
from src.ranking_generator import generate_all_matches


def _pl(n): return Player(name=n, surname="")
def _pair(name, **kw):
    return Pair(name=name, player_1=_pl(f"{name}A"), player_2=_pl(f"{name}B"), **kw)


def _phase(groups, **kw):
    defaults = dict(
        name="PF Test",
        start_date=date(2026, 6, 1),   # lunes
        end_date=date(2026, 6, 30),
        groups=groups,
        courts=[Court(id=f"court_{i}", name=f"Pista {i}") for i in range(1, 6)],
        bookings=[],
        match_duration_minutes=90,
        day_start_time=time(16, 0),
        day_end_time=time(22, 30),
        max_matches_per_week=10,
        min_days_between_matches=0,
        random_seed=42,
    )
    defaults.update(kw)
    return RankingPhase(**defaults)


class TestFixedCourtHonored:

    def test_both_pairs_pf_same_slot_assigned_there(self):
        # Miércoles (weekday=2) a las 20:30 — ambas parejas con la misma PF
        p1 = _pair("AA", preferred_weekday=2, preferred_time=time(20, 30))
        p2 = _pair("BB", preferred_weekday=2, preferred_time=time(20, 30))
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])
        matches = generate_all_matches([g])
        result = Scheduler(phase).schedule(matches)

        assert len(result.scheduled) == 1
        m = result.scheduled[0]
        assert m.suggested_date.weekday() == 2, "Debe caer en miércoles"
        assert m.suggested_start_time == time(20, 30), "Debe caer a las 20:30 (PF)"

    def test_single_pf_pair_match_lands_on_pf_slot(self):
        # Solo una pareja con PF; la otra disponible toda la semana
        p1 = _pair("AA", preferred_weekday=3, preferred_time=time(21, 0))  # jueves 21:00
        p2 = _pair("BB")  # sin restricción
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])
        matches = generate_all_matches([g])
        result = Scheduler(phase).schedule(matches)

        m = result.scheduled[0]
        assert m.suggested_date.weekday() == 3
        assert m.suggested_start_time == time(21, 0)

    def test_pf_not_displaced_by_late_hour_penalty(self):
        # PF tardío (22:00) — la penalización por hora tardía NO debe moverlo
        p1 = _pair("AA", preferred_weekday=1, preferred_time=time(21, 0))  # martes 21:00
        p2 = _pair("BB", preferred_weekday=1, preferred_time=time(21, 0))
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        m = result.scheduled[0]
        assert m.suggested_start_time == time(21, 0)

    def test_pf_deterministic_across_runs(self):
        # Mismo seed → mismo resultado, y siempre en la PF
        p1 = _pair("AA", preferred_weekday=2, preferred_time=time(20, 0))
        p2 = _pair("BB", preferred_weekday=2, preferred_time=time(20, 0))
        g = Group(name="G", pairs=[p1, p2])
        results = []
        for _ in range(3):
            phase = _phase([g])
            r = Scheduler(phase).schedule(generate_all_matches([g]))
            results.append((r.scheduled[0].suggested_date, r.scheduled[0].suggested_start_time))
        assert all(r == results[0] for r in results)
        assert results[0][1] == time(20, 0)


class TestPFDoesNotBreakNonPF:

    def test_non_pf_matches_still_scheduled(self):
        # Grupo sin PF se sigue planificando con normalidad
        pairs = [_pair(f"P{i}") for i in range(4)]
        g = Group(name="G", pairs=pairs)
        phase = _phase([g])
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        # C(4,2)=6 partidos, todos asignables con 5 pistas y mes completo
        assert len(result.scheduled) == 6

    def test_mixed_pf_and_non_pf_group(self):
        p1 = _pair("AA", preferred_weekday=2, preferred_time=time(20, 30))
        p2 = _pair("BB", preferred_weekday=2, preferred_time=time(20, 30))
        p3 = _pair("CC")
        p4 = _pair("DD")
        g = Group(name="G", pairs=[p1, p2, p3, p4])
        phase = _phase([g])
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        # El partido AA vs BB debe estar en su PF
        aa_bb = next(
            (m for m in result.scheduled
             if {m.pair_1.name, m.pair_2.name} == {"AA", "BB"}),
            None,
        )
        assert aa_bb is not None
        assert aa_bb.suggested_date.weekday() == 2
        assert aa_bb.suggested_start_time == time(20, 30)
