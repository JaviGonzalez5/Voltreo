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


class TestConflictingPF:
    """Dos parejas con PF en franjas distintas que juegan entre sí."""

    def test_match_lands_on_one_of_the_two_pf_slots(self):
        # AA: martes 19:30 ; BB: miércoles 20:00 — juegan entre sí
        p1 = _pair("AA", preferred_weekday=1, preferred_time=time(19, 30))
        p2 = _pair("BB", preferred_weekday=2, preferred_time=time(20, 0))
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        m = result.scheduled[0]
        # Debe caer en UNA de las dos franjas fijas, no en un hueco arbitrario
        on_aa = (m.suggested_date.weekday() == 1 and m.suggested_start_time == time(19, 30))
        on_bb = (m.suggested_date.weekday() == 2 and m.suggested_start_time == time(20, 0))
        assert on_aa or on_bb, (
            f"Asignado a {m.suggested_date.weekday()} {m.suggested_start_time}, "
            "debería estar en una de las dos PF"
        )

    def test_validator_does_not_flag_when_on_opponent_pf(self):
        from src.schedule_validator import validate_schedule
        p1 = _pair("AA", preferred_weekday=1, preferred_time=time(19, 30))
        p2 = _pair("BB", preferred_weekday=2, preferred_time=time(20, 0))
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        violations = validate_schedule(result, phase)
        pf_violations = [v for v in violations if v["type"] == "preferred_slot_mismatch"]
        # El partido cae en la PF de una pareja → no debe haber infracción PF
        assert pf_violations == [], f"No debería marcar PF: {pf_violations}"


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


class TestMultiPFValidation:

    def test_validator_accepts_second_pf_slot(self):
        """
        Si una pareja tiene dos PF, un partido en la segunda franja NO debe
        marcarse como "PF no respetada".
        """
        from src.models import Match, ScheduleResult
        from src.schedule_validator import validate_schedule

        p1 = _pair(
            "AA",
            preferred_weekday=1,
            preferred_time=time(19, 30),
            preferred_slots=[
                {"weekday": 1, "time": time(19, 30)},  # martes
                {"weekday": 3, "time": time(20, 30)},  # jueves
            ],
        )
        p2 = _pair("BB")
        g = Group(name="G", pairs=[p1, p2])
        phase = _phase([g])

        m = Match(
            group_id=g.id,
            group_name=g.name,
            pair_1=p1,
            pair_2=p2,
            suggested_date=date(2026, 6, 4),   # jueves
            suggested_start_time=time(20, 30),
            suggested_end_time=time(22, 0),
            court=phase.courts[0],
            status=MatchStatus.SCHEDULED,
        )
        result = ScheduleResult(scheduled=[m], conflicts=[], total_matches=1)

        violations = validate_schedule(result, phase)
        pf_violations = [v for v in violations if v["type"] == "preferred_slot_mismatch"]
        assert pf_violations == [], pf_violations


class TestMidnightClose:
    """Hora de cierre 00:00 = medianoche (fin del día), no inicio del día."""

    def test_day_end_helper_treats_midnight_as_end(self):
        from datetime import date as _d, time as _t, datetime as _dt
        from src.scheduler import _day_end_dt
        # 00:00 -> medianoche del día siguiente
        assert _day_end_dt(_d(2026, 6, 1), _t(0, 0)) == _dt(2026, 6, 2, 0, 0)
        # Otras horas, igual que combine normal
        assert _day_end_dt(_d(2026, 6, 1), _t(22, 30)) == _dt(2026, 6, 1, 22, 30)

    def test_ranking_schedules_until_midnight(self):
        p = [_pair(f"P{i}") for i in range(4)]
        g = Group(name="G", pairs=p)
        phase = _phase([g], day_start_time=time(20, 0), day_end_time=time(0, 0),
                       match_duration_minutes=90)
        result = Scheduler(phase).schedule(generate_all_matches([g]))
        assert len(result.scheduled) == 6  # todos caben en la franja 20:00–00:00
        # Alguno puede empezar a las 22:30 (termina justo a 00:00)
        assert all(m.suggested_end_time is not None for m in result.scheduled)


# ---------------------------------------------------------------------------
# Regresión: las franjas PF de preferred_slots sobreviven al round-trip de BD
# (su 'time' se serializa a string; antes se perdían y salían 0 en pista fija).
# ---------------------------------------------------------------------------

def test_pf_slots_survive_db_round_trip():
    from src.scheduler import _pair_pf_slots
    import src.schedule_validator as _sv

    p = _pair("multi",
              preferred_weekday=2, preferred_time=time(20, 30),
              preferred_slots=[{"weekday": 2, "time": time(20, 30)},
                               {"weekday": 4, "time": time(19, 0)}])
    g = Group(name="A", pairs=[p])

    # Round-trip JSON como hace la base de datos
    g2 = Group.model_validate(g.model_dump(mode="json"))
    p2 = g2.pairs[0]

    # preferred_slots['time'] vuelve como string tras el round-trip…
    assert isinstance(p2.preferred_slots[0]["time"], str)
    # …pero _pair_pf_slots debe reconstruir AMBAS franjas (scheduler y validador)
    assert set(_pair_pf_slots(p2)) == {(2, time(20, 30)), (4, time(19, 0))}
    assert set(_sv._pair_pf_slots(p2)) == {(2, time(20, 30)), (4, time(19, 0))}


def test_coerce_time_accepts_str_and_time():
    from src.scheduler import _coerce_time
    assert _coerce_time(time(20, 30)) == time(20, 30)
    assert _coerce_time("20:30") == time(20, 30)
    assert _coerce_time("20:30:00") == time(20, 30)
    assert _coerce_time("") is None
    assert _coerce_time(None) is None
    assert _coerce_time("nonsense") is None
