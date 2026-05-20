"""
Asigna horarios a los partidos pendientes respetando:
- Disponibilidad de pistas.
- Reservas ya existentes en Syltek.
- Una pareja no juega dos partidos a la misma hora.
- Una pista no tiene dos partidos simultáneos.
- Separación mínima de N días entre partidos de la misma pareja.
- Distribución equilibrada de días, horas y pistas (scoring).
"""

from collections import defaultdict
from datetime import date, time, datetime, timedelta
import random

from .models import (
    Match,
    Court,
    Booking,
    AvailabilitySlot,
    MatchStatus,
    Conflict,
    ScheduleResult,
    RankingPhase,
    BalanceWeights,
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _overlaps(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    """True si los dos intervalos se solapan (excluyendo contacto en los extremos)."""
    return s1 < e2 and s2 < e1


def _booking_belongs_to_court(booking: Booking, court: Court) -> bool:
    """
    Comprueba si una reserva de Syltek corresponde a una pista del scheduler.

    Syltek usa IDs numéricos ('1477') y nombres 'Padel 1',
    el scheduler usa IDs internos ('court_1') y nombres 'Pista 1'.
    Se intenta la coincidencia en tres niveles:
      1. court_id exacto (útil si se importan con el mismo ID)
      2. court_name exacto (case-insensitive)
      3. número extraído del nombre  ('Padel 3' ↔ 'Pista 3' → ambos tienen el 3)
    """
    import re as _re
    # 1. ID exacto
    if booking.court_id == court.id:
        return True
    # 2. Nombre exacto (case-insensitive, sin espacios extra)
    if booking.court_name.strip().lower() == court.name.strip().lower():
        return True
    # 3. Número extraído del nombre
    b_nums = _re.findall(r"\d+", booking.court_name)
    c_nums = _re.findall(r"\d+", court.name)
    if b_nums and c_nums and b_nums[-1] == c_nums[-1]:
        return True
    return False


def build_availability_slots(
    courts: list[Court],
    phase: RankingPhase,
    bookings: list[Booking],
) -> list[AvailabilitySlot]:
    """
    Genera todos los huecos disponibles en cada pista para cada día de la fase,
    divididos en bloques de match_duration_minutes, respetando las reservas existentes.

    Las reservas se asocian a pistas por ID, nombre exacto o número del nombre
    para cubrir el caso en que Syltek usa 'Padel N' y el scheduler 'Pista N'.
    """
    slots: list[AvailabilitySlot] = []
    duration = timedelta(minutes=phase.match_duration_minutes)
    current = phase.start_date

    while current <= phase.end_date:
        for court in courts:
            if not court.active:
                continue

            day_bookings = [
                b for b in bookings
                if _booking_belongs_to_court(b, court)
                and b.start_datetime.date() == current
            ]

            slot_start = _dt(current, phase.day_start_time)
            day_end = _dt(current, phase.day_end_time)

            while slot_start + duration <= day_end:
                slot_end = slot_start + duration
                blocked = any(
                    _overlaps(slot_start, slot_end, b.start_datetime, b.end_datetime)
                    for b in day_bookings
                )
                if not blocked:
                    slots.append(
                        AvailabilitySlot(
                            court=court,
                            date=current,
                            start_time=slot_start.time(),
                            end_time=slot_end.time(),
                        )
                    )
                slot_start += duration

        current += timedelta(days=1)

    return slots


# ---------------------------------------------------------------------------
# Scheduler con scoring
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Planificador con scoring.

    Algoritmo:
    1. Genera todos los slots libres respetando las reservas.
    2. Para cada partido (en un orden mezclado pero estable con seed):
       a. Filtra los slots que cumplen restricciones DURAS:
          - pista no ocupada en ese slot
          - ninguna pareja con partido solapado
          - ambas parejas por debajo de max_matches_per_week
          - ambas parejas respetan min_days_between_matches
       b. Puntúa cada slot candidato con BalanceWeights:
          - penaliza repetir misma hora / mismo día semana / misma pista
          - penaliza días y pistas ya cargados
          - bonus leve por programar pronto
       c. Asigna el slot con MENOR penalización (=mejor).
    3. Si ningún slot cumple las restricciones duras → conflicto.
    """

    def __init__(self, phase: RankingPhase):
        self.phase = phase
        self.duration = timedelta(minutes=phase.match_duration_minutes)
        self.weights: BalanceWeights = phase.balance_weights
        # RNG determinista si hay seed
        self._rng = random.Random(phase.random_seed) if phase.random_seed is not None else random.Random()

    # -------------------------------------------------------------------
    # Métodos auxiliares
    # -------------------------------------------------------------------

    @staticmethod
    def _week_num(d: date) -> int:
        return d.isocalendar()[1]

    @staticmethod
    def _hour_bucket(t: time) -> int:
        """Agrupa las horas en franjas (cada bucket = 1 hora)."""
        return t.hour

    def _pair_conflicts_existing(
        self,
        pair_id: str,
        d: date,
        start: time,
        end: time,
        pair_schedule: dict[str, list[tuple[date, time, time, str]]],
    ) -> bool:
        """¿La pareja ya tiene un partido que solape con este slot?"""
        for ps_date, ps_start, ps_end, _ in pair_schedule[pair_id]:
            if ps_date != d:
                continue
            if _overlaps(_dt(d, start), _dt(d, end), _dt(ps_date, ps_start), _dt(ps_date, ps_end)):
                return True
        return False

    @staticmethod
    def _pair_available(pair, d: date, st: time) -> bool:
        """Comprueba si la pareja está disponible ese día y hora según sus Observaciones."""
        from .models import Pair as PairModel
        if not isinstance(pair, PairModel):
            return True
        # Días de la semana
        if pair.available_weekdays and d.weekday() not in pair.available_weekdays:
            return False
        # Hora mínima
        if pair.available_from and st < pair.available_from:
            return False
        # Hora máxima
        if pair.available_until and st >= pair.available_until:
            return False
        return True

    def _violates_min_days(
        self,
        pair_id: str,
        d: date,
        pair_schedule: dict[str, list[tuple[date, time, time, str]]],
    ) -> bool:
        """¿Asignar este día rompe la separación mínima con otros partidos de la pareja?"""
        min_days = self.phase.min_days_between_matches
        if min_days <= 0:
            return False
        for ps_date, *_ in pair_schedule[pair_id]:
            if abs((ps_date - d).days) < min_days:
                return True
        return False

    def _slot_score(
        self,
        slot: AvailabilitySlot,
        p1_id: str,
        p2_id: str,
        pair_schedule: dict[str, list[tuple[date, time, time, str]]],
        day_load: dict[date, int],
        court_load: dict[str, int],
        pair_1=None,
        pair_2=None,
    ) -> float:
        """
        Calcula penalización del slot. Menor = mejor.
        Combina factores de equilibrio configurables en BalanceWeights.
        """
        w = self.weights
        score = 0.0
        hour_b = self._hour_bucket(slot.start_time)
        weekday = slot.date.weekday()
        court_id = slot.court.id

        # Penalizaciones por repetición para AMBAS parejas
        for pid in (p1_id, p2_id):
            for ps_date, ps_start, _ps_end, ps_court in pair_schedule[pid]:
                if self._hour_bucket(ps_start) == hour_b:
                    score += w.same_hour_penalty
                if ps_date.weekday() == weekday:
                    score += w.same_weekday_penalty
                if ps_court == court_id:
                    score += w.same_court_penalty

        # Penalización por carga del día y de la pista (preferimos repartir)
        score += day_load[slot.date] * w.day_load_penalty
        score += court_load[court_id] * w.court_load_penalty

        # Bonus leve por programar pronto en la fase (resta puntuación)
        days_offset = (slot.date - self.phase.start_date).days
        score -= max(0, 30 - days_offset) * (w.early_day_bonus / 30.0)

        # Bonus fuerte si el slot coincide con la pista fija de alguna pareja
        preferred_bonus = getattr(w, "preferred_slot_bonus", 25.0)
        for pair in (pair_1, pair_2):
            if pair is None:
                continue
            pw = getattr(pair, "preferred_weekday", None)
            pt = getattr(pair, "preferred_time", None)
            if pw is not None and slot.date.weekday() == pw:
                score -= preferred_bonus
            if pt is not None and slot.start_time == pt:
                score -= preferred_bonus

        return score

    # -------------------------------------------------------------------
    # Bucle principal
    # -------------------------------------------------------------------

    def schedule(self, matches: list[Match]) -> ScheduleResult:
        slots = build_availability_slots(
            courts=self.phase.courts,
            phase=self.phase,
            bookings=self.phase.bookings,
        )
        slots.sort(key=lambda s: (s.date, s.start_time, s.court.name))

        # Orden de partidos: mezclar entre grupos pero manteniendo equidad
        shuffled = list(matches)
        self._rng.shuffle(shuffled)
        group_order = list(dict.fromkeys(m.group_id for m in shuffled))
        shuffled.sort(key=lambda m: group_order.index(m.group_id))

        # Estado
        occupied_slots: set[tuple[str, date, time]] = set()
        pair_schedule: dict[str, list[tuple[date, time, time, str]]] = defaultdict(list)
        pair_weekly_count: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        day_load: dict[date, int] = defaultdict(int)
        court_load: dict[str, int] = defaultdict(int)
        # Jugadores con partido ya asignado ese día (cubre jugadores en varios rankings)
        player_day_set: dict[str, set[date]] = defaultdict(set)

        scheduled: list[Match] = []
        conflicts: list[Match] = []
        conflict_details: list[Conflict] = []

        for match in shuffled:
            p1_id = match.pair_1.id
            p2_id = match.pair_2.id
            # IDs de los 4 jugadores individuales del partido
            player_ids = [
                match.pair_1.player_1.id, match.pair_1.player_2.id,
                match.pair_2.player_1.id, match.pair_2.player_2.id,
            ]

            # Filtrar candidatos por restricciones duras
            candidates: list[AvailabilitySlot] = []
            for slot in slots:
                cid = slot.court.id
                d = slot.date
                st = slot.start_time
                et = slot.end_time

                if (cid, d, st) in occupied_slots:
                    continue
                if self._pair_conflicts_existing(p1_id, d, st, et, pair_schedule):
                    continue
                if self._pair_conflicts_existing(p2_id, d, st, et, pair_schedule):
                    continue
                # Ningún jugador puede tener dos partidos el mismo día (cross-ranking)
                if any(d in player_day_set[pid] for pid in player_ids):
                    continue
                wk = self._week_num(d)
                if pair_weekly_count[p1_id][wk] >= self.phase.max_matches_per_week:
                    continue
                if pair_weekly_count[p2_id][wk] >= self.phase.max_matches_per_week:
                    continue
                if self._violates_min_days(p1_id, d, pair_schedule):
                    continue
                if self._violates_min_days(p2_id, d, pair_schedule):
                    continue
                # Disponibilidad de la pareja (días y horario de Observaciones)
                if not self._pair_available(match.pair_1, d, st):
                    continue
                if not self._pair_available(match.pair_2, d, st):
                    continue

                candidates.append(slot)

            if not candidates:
                match.status = MatchStatus.CONFLICT
                match.conflict_reason = (
                    "Sin huecos compatibles: revisa max_matches_per_week, "
                    "min_days_between_matches, horario y reservas existentes."
                )
                conflicts.append(match)
                conflict_details.append(
                    Conflict.model_construct(
                        match_id=match.id,
                        match_label=match.label,
                        reason=match.conflict_reason,
                        pair_ids_involved=[p1_id, p2_id],
                    )
                )
                continue

            # Elegir el slot con MENOR penalización
            best = min(
                candidates,
                key=lambda s: self._slot_score(
                    s, p1_id, p2_id, pair_schedule, day_load, court_load,
                    pair_1=match.pair_1, pair_2=match.pair_2,
                ),
            )

            # Asignar
            match.suggested_date = best.date
            match.suggested_start_time = best.start_time
            match.suggested_end_time = best.end_time
            match.court = best.court
            match.status = MatchStatus.SCHEDULED
            match.conflict_reason = None

            occupied_slots.add((best.court.id, best.date, best.start_time))
            pair_schedule[p1_id].append((best.date, best.start_time, best.end_time, best.court.id))
            pair_schedule[p2_id].append((best.date, best.start_time, best.end_time, best.court.id))
            pair_weekly_count[p1_id][self._week_num(best.date)] += 1
            pair_weekly_count[p2_id][self._week_num(best.date)] += 1
            for pid in player_ids:
                player_day_set[pid].add(best.date)
            day_load[best.date] += 1
            court_load[best.court.id] += 1

            scheduled.append(match)

        courts_used = list({m.court.name for m in scheduled if m.court})

        return ScheduleResult.model_construct(
            scheduled=scheduled,
            conflicts=conflicts,
            total_matches=len(matches),
            courts_used=courts_used,
            conflict_details=conflict_details,
        )


def pairs_with_most_conflicts(result: ScheduleResult) -> list[tuple[str, int]]:
    """Devuelve parejas ordenadas por número de conflictos descendente."""
    count: dict[str, int] = defaultdict(int)
    for c in result.conflict_details:
        for pid in c.pair_ids_involved:
            count[pid] += 1
    return sorted(count.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Métricas de balanceo (útiles para la página Revisión)
# ---------------------------------------------------------------------------

def balance_metrics(result: ScheduleResult) -> dict:
    """
    Calcula métricas de equilibrio del calendario generado.
    Útil para mostrar en la página Revisión y comparar configuraciones.
    """
    if not result.scheduled:
        return {"hour_distribution": {}, "weekday_distribution": {}, "court_distribution": {}}

    hour_dist: dict[int, int] = defaultdict(int)
    weekday_dist: dict[int, int] = defaultdict(int)
    court_dist: dict[str, int] = defaultdict(int)

    for m in result.scheduled:
        if m.suggested_start_time:
            hour_dist[m.suggested_start_time.hour] += 1
        if m.suggested_date:
            weekday_dist[m.suggested_date.weekday()] += 1
        if m.court:
            court_dist[m.court.name] += 1

    return {
        "hour_distribution": dict(sorted(hour_dist.items())),
        "weekday_distribution": dict(sorted(weekday_dist.items())),
        "court_distribution": dict(court_dist),
    }
