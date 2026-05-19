"""Tests del planificador de horarios."""
import pytest
from datetime import date, time

from src.models import (
    Court, Group, Pair, Player, RankingPhase, MatchStatus, Booking
)
from src.ranking_generator import generate_all_matches
from src.scheduler import Scheduler, build_availability_slots


def make_court(n: int) -> Court:
    return Court(id=f"court_{n}", name=f"Pista {n}", active=True)


def make_pair(name: str, group_id: str) -> Pair:
    p1 = Player(name=f"{name}_A")
    p2 = Player(name=f"{name}_B")
    return Pair(name=name, player_1=p1, player_2=p2, group_id=group_id)


def make_group(n_pairs: int, gid: str = "g1") -> Group:
    pairs = [make_pair(f"P{i}", gid) for i in range(n_pairs)]
    return Group(id=gid, name=f"Grupo {gid}", pairs=pairs)


def make_phase(
    n_courts: int = 4,
    n_days: int = 14,
    n_pairs_per_group: int = 6,
    max_per_week: int = 2,
    groups: list[Group] | None = None,
) -> RankingPhase:
    courts = [make_court(i) for i in range(1, n_courts + 1)]
    start = date(2025, 6, 2)
    from datetime import timedelta
    end = start + timedelta(days=n_days - 1)
    if groups is None:
        groups = [make_group(n_pairs_per_group)]
    return RankingPhase(
        name="Test Phase",
        start_date=start,
        end_date=end,
        courts=courts,
        groups=groups,
        match_duration_minutes=90,
        day_start_time=time(16, 0),
        day_end_time=time(22, 30),
        max_matches_per_week=max_per_week,
        # Para no romper tests previos: sin restricción extra.
        # Los tests específicos del nuevo comportamiento se añaden abajo.
        min_days_between_matches=0,
        random_seed=42,
    )


class TestBuildAvailabilitySlots:
    def test_slots_generated(self):
        phase = make_phase(n_courts=2, n_days=1)
        slots = build_availability_slots(phase.courts, phase, bookings=[])
        # 16:00–22:30 con bloques de 90min = 4 bloques por pista × 2 pistas
        assert len(slots) == 8

    def test_booking_blocks_slot(self):
        phase = make_phase(n_courts=1, n_days=1)
        booking = Booking(
            court_id="court_1",
            court_name="Pista 1",
            start_datetime=__import__("datetime").datetime(2025, 6, 2, 16, 0),
            end_datetime=__import__("datetime").datetime(2025, 6, 2, 17, 30),
        )
        slots = build_availability_slots(phase.courts, phase, bookings=[booking])
        # El primer bloque está bloqueado, quedan 3
        assert len(slots) == 3


class TestScheduler:
    def test_all_matches_scheduled_with_enough_space(self):
        """Con 4 pistas y 21 días debe poder programar el round-robin completo (6 parejas)."""
        group = make_group(6, "g1")
        # 5 partidos por pareja en 3 semanas con max=2/sem ⇒ holgura suficiente.
        phase = make_phase(n_courts=4, n_days=21, groups=[group], max_per_week=2)
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)
        assert result.conflict_count == 0
        assert result.scheduled_count == 15

    def test_no_pair_plays_twice_same_slot(self):
        group = make_group(6, "g1")
        phase = make_phase(n_courts=4, n_days=14, groups=[group])
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)

        from collections import defaultdict
        pair_slots: dict[str, list] = defaultdict(list)
        for m in result.scheduled:
            for pid in [m.pair_1.id, m.pair_2.id]:
                pair_slots[pid].append((m.suggested_date, m.suggested_start_time))

        for pid, slots in pair_slots.items():
            assert len(slots) == len(set(slots)), f"Pareja {pid} juega dos veces en el mismo slot"

    def test_no_court_double_booked(self):
        groups = [make_group(6, f"g{i}") for i in range(3)]
        phase = make_phase(n_courts=4, n_days=21, groups=groups)
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)

        from collections import defaultdict
        court_slots: dict[str, set] = defaultdict(set)
        for m in result.scheduled:
            key = (m.suggested_date, m.suggested_start_time)
            cid = m.court.id if m.court else "none"
            assert key not in court_slots[cid], f"Pista {cid} doblemente reservada en {key}"
            court_slots[cid].add(key)

    def test_conflicts_flagged_when_no_space(self):
        """Con solo 1 día y 1 pista no caben 15 partidos."""
        group = make_group(6, "g1")
        phase = make_phase(n_courts=1, n_days=1, groups=[group])
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)
        assert result.conflict_count > 0
        for m in result.conflicts:
            assert m.status == MatchStatus.CONFLICT
            assert m.conflict_reason is not None

    def test_result_totals_correct(self):
        group = make_group(4, "g1")
        phase = make_phase(n_courts=4, n_days=7, groups=[group])
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)
        assert result.total_matches == len(matches)
        assert result.scheduled_count + result.conflict_count == result.total_matches


class TestSchedulerBalance:
    """Tests del nuevo scheduler con scoring."""

    def test_deterministic_with_seed(self):
        """Con la misma seed, dos ejecuciones dan exactamente el mismo resultado."""
        group = make_group(6, "g1")
        phase1 = make_phase(n_courts=4, n_days=21, groups=[group])
        phase2 = make_phase(n_courts=4, n_days=21, groups=[group])

        matches1 = generate_all_matches(phase1.groups)
        matches2 = generate_all_matches(phase2.groups)

        r1 = Scheduler(phase1).schedule(matches1)
        r2 = Scheduler(phase2).schedule(matches2)

        sig1 = [(m.suggested_date, m.suggested_start_time, m.court.id if m.court else None)
                for m in r1.scheduled]
        sig2 = [(m.suggested_date, m.suggested_start_time, m.court.id if m.court else None)
                for m in r2.scheduled]
        assert sig1 == sig2, "El scheduler con seed fija debe ser determinista"

    def test_min_days_between_matches_respected(self):
        """Con min_days=3, no debe haber dos partidos de la misma pareja a menos de 3 días."""
        group = make_group(6, "g1")
        phase = make_phase(n_courts=4, n_days=30, groups=[group], max_per_week=3)
        phase.min_days_between_matches = 3
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)

        from collections import defaultdict
        pair_dates: dict[str, list] = defaultdict(list)
        for m in result.scheduled:
            for pid in [m.pair_1.id, m.pair_2.id]:
                pair_dates[pid].append(m.suggested_date)

        for pid, dates in pair_dates.items():
            dates_sorted = sorted(dates)
            for i in range(1, len(dates_sorted)):
                gap = (dates_sorted[i] - dates_sorted[i - 1]).days
                assert gap >= 3, (
                    f"Pareja {pid} tiene partidos a {gap} días: {dates_sorted}"
                )

    def test_balance_spreads_courts(self):
        """El scoring debe repartir entre pistas, no usar siempre la 1."""
        group = make_group(6, "g1")
        phase = make_phase(n_courts=4, n_days=21, groups=[group])
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)

        from collections import Counter
        court_use = Counter(m.court.id for m in result.scheduled if m.court)
        # Esperamos uso de al menos 2 pistas distintas (idealmente las 4)
        assert len(court_use) >= 2, f"Sólo se usaron pistas: {court_use}"

    def test_balance_metrics_returns_distributions(self):
        from src.scheduler import balance_metrics
        group = make_group(6, "g1")
        phase = make_phase(n_courts=4, n_days=21, groups=[group])
        matches = generate_all_matches(phase.groups)
        result = Scheduler(phase).schedule(matches)
        m = balance_metrics(result)
        assert "hour_distribution" in m
        assert "weekday_distribution" in m
        assert "court_distribution" in m
        assert sum(m["court_distribution"].values()) == result.scheduled_count
