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
    # 1. ID exacto
    if booking.court_id == court.id:
        return True
    # 2. Nombre exacto (case-insensitive, sin espacios extra)
    if booking.court_name.strip().lower() == court.name.strip().lower():
        return True
    # 3. Número extraído del nombre
    b_nums = re.findall(r"\d+", booking.court_name)
    c_nums = re.findall(r"\d+", court.name)
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

    # Precompute: for each active court, collect its bookings grouped by date.
    # This replaces an O(bookings * courts * days) scan with a single O(bookings * courts) pass.
    active_courts = [c for c in courts if c.active]
    court_day_bookings: dict[str, dict] = {c.id: defaultdict(list) for c in active_courts}
    for b in bookings:
        for court in active_courts:
            if _booking_belongs_to_court(b, court):
                court_day_bookings[court.id][b.start_datetime.date()].append(b)
                break  # a booking belongs to at most one court

    while current <= phase.end_date:
        # ── El ranking solo se juega de lunes a viernes
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        for court in active_courts:
            day_bookings = court_day_bookings[court.id].get(current, [])

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
        """
        Comprueba si la pareja está disponible ese día y hora según sus Observaciones.

        Lógica:
        1. PF override: si el slot coincide con preferred_weekday + preferred_time → siempre OK.
        2. Días disponibles: si hay lista y el weekday no está → NO.
        3. Per-day window: si hay ventana para ese día, aplicarla.
        4. Fallback global: available_from / available_until.
        Nota: available_until es hora máxima de INICIO (inclusiva) → st > until bloquea.
        """
        from .models import Pair as PairModel
        if not isinstance(pair, PairModel):
            return True

        wd = d.weekday()

        # ── PF override: la hora de pista fija siempre es válida
        pw = getattr(pair, "preferred_weekday", None)
        pt = getattr(pair, "preferred_time", None)
        if pw is not None and pt is not None and wd == pw and st == pt:
            return True

        # ── Días de la semana
        if pair.available_weekdays and wd not in pair.available_weekdays:
            return False

        # ── Ventana por día (tiene prioridad sobre global)
        pdw = getattr(pair, "per_day_windows", {})
        if pdw and wd in pdw:
            win = pdw[wd]
            wf  = win.get("from")
            wu  = win.get("until")
            if wf is not None and st < wf:
                return False
            # until es hora máxima de INICIO inclusiva → solo bloquea si st > until
            if wu is not None and st > wu:
                return False
            return True

        # ── Ventana global
        if pair.available_from and st < pair.available_from:
            return False
        if pair.available_until and st > pair.available_until:
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
        hour_load: dict[int, int] | None = None,
        weekday_load: dict[int, int] | None = None,
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
        score += day_load.get(slot.date, 0) * w.day_load_penalty
        score += court_load.get(court_id, 0) * w.court_load_penalty

        # Penalizaciones GLOBALES: evitan que todos los partidos se amontonen
        # en la misma hora/día aunque sea la primera vez de cada pareja.
        if hour_load is not None:
            score += hour_load.get(hour_b, 0) * w.global_hour_penalty
        if weekday_load is not None:
            score += weekday_load.get(weekday, 0) * w.global_weekday_penalty

        # Bonus leve por programar pronto en la fase (resta puntuación)
        days_offset = (slot.date - self.phase.start_date).days
        score -= max(0, 30 - days_offset) * (w.early_day_bonus / 30.0)

        # Bonus fuerte si el slot coincide con la pista fija de alguna pareja.
        # Bonus parcial si solo coincide día o solo hora; bonus doble si coincide exacto.
        preferred_bonus = getattr(w, "preferred_slot_bonus", 25.0)
        for pair in (pair_1, pair_2):
            if pair is None:
                continue
            pw = getattr(pair, "preferred_weekday", None)
            pt = getattr(pair, "preferred_time", None)
            day_match  = pw is not None and slot.date.weekday() == pw
            time_match = pt is not None and slot.start_time == pt
            if day_match or time_match:
                score -= preferred_bonus
            if day_match and time_match:
                score -= preferred_bonus  # bonus adicional por coincidencia exacta día+hora

        return score

    # -------------------------------------------------------------------
    # Auxiliar: dificultad de restricción de un partido
    # -------------------------------------------------------------------

    def _constraint_difficulty(self, match: Match) -> int:
        """
        Cuánto de difícil es asignar este partido (mayor = más restrictivo).
        Los partidos más difíciles se procesan primero para que tengan más
        opciones de slot disponibles.
        """
        score = 0
        for pair in (match.pair_1, match.pair_2):
            if pair.available_weekdays:
                # Menos días disponibles = más difícil
                score += (7 - len(pair.available_weekdays)) * 20
            if pair.available_from:
                # Hora de inicio tardía = menos slots válidos
                score += pair.available_from.hour * 3
            if pair.available_until:
                # Ventana muy estrecha (e.g. solo 1 hora)
                if pair.available_from:
                    window_h = pair.available_until.hour - pair.available_from.hour
                    score += max(0, 4 - window_h) * 10
        return score

    # -------------------------------------------------------------------
    # Auxiliar: buscar el mejor slot con flags de relajación
    # -------------------------------------------------------------------

    def _find_best_slot(
        self,
        match: Match,
        slots: list[AvailabilitySlot],
        occupied_slots: set,
        pair_schedule: dict,
        pair_weekly_count: dict,
        day_load: dict,
        court_load: dict,
        player_day_set: dict,
        hour_load: dict | None = None,
        weekday_load: dict | None = None,
        *,
        relax_min_days: bool = False,
        relax_max_week: bool = False,
        relax_availability: bool = False,
        relax_cross_player: bool = False,
    ):
        """
        Devuelve el mejor AvailabilitySlot (o None si no hay candidatos).

        Variedad controlada y reproducible:
        · Los candidatos se ordenan por score (menor = mejor).
        · Se elige aleatoriamente entre los top-N con el RNG semillado del scheduler,
          lo que da variedad real pero resultados reproducibles con la misma seed.
        · N viene de BalanceWeights.top_candidates_pool (por defecto 6).
        """
        p1_id = match.pair_1.id
        p2_id = match.pair_2.id
        player_ids = [
            match.pair_1.player_1.id, match.pair_1.player_2.id,
            match.pair_2.player_1.id, match.pair_2.player_2.id,
        ]

        candidates: list[AvailabilitySlot] = []
        for slot in slots:
            cid = slot.court.id
            d   = slot.date
            st  = slot.start_time
            et  = slot.end_time

            # ── Restricciones FÍSICAS (nunca se relajan)
            if (cid, d, st) in occupied_slots:
                continue
            if self._pair_conflicts_existing(p1_id, d, st, et, pair_schedule):
                continue
            if self._pair_conflicts_existing(p2_id, d, st, et, pair_schedule):
                continue

            # ── Cross-ranking: jugador no juega dos veces el mismo día
            if not relax_cross_player:
                if any(d in player_day_set[pid] for pid in player_ids):
                    continue

            # ── Máximo partidos por semana (restricción dura, nunca se relaja)
            wk = self._week_num(d)
            if not relax_max_week:
                if pair_weekly_count[p1_id][wk] >= self.phase.max_matches_per_week:
                    continue
                if pair_weekly_count[p2_id][wk] >= self.phase.max_matches_per_week:
                    continue

            # ── Separación mínima entre partidos
            if not relax_min_days:
                if self._violates_min_days(p1_id, d, pair_schedule):
                    continue
                if self._violates_min_days(p2_id, d, pair_schedule):
                    continue

            # ── Disponibilidad declarada (NUNCA se relaja — relax_availability siempre False)
            if not relax_availability:
                if not self._pair_available(match.pair_1, d, st):
                    continue
                if not self._pair_available(match.pair_2, d, st):
                    continue

            candidates.append(slot)

        if not candidates:
            return None

        # ── Ordenar por score y elegir aleatoriamente entre los top-N
        def _score(s):
            return self._slot_score(
                s, p1_id, p2_id, pair_schedule, day_load, court_load,
                hour_load=hour_load, weekday_load=weekday_load,
                pair_1=match.pair_1, pair_2=match.pair_2,
            )

        candidates.sort(key=_score)
        pool_size = min(getattr(self.weights, "top_candidates_pool", 6), len(candidates))
        return self._rng.choice(candidates[:pool_size])

    # -------------------------------------------------------------------
    # Auxiliar: aplicar asignación al estado compartido
    # -------------------------------------------------------------------

    def _apply_assignment(
        self,
        match: Match,
        best: AvailabilitySlot,
        occupied_slots: set,
        pair_schedule: dict,
        pair_weekly_count: dict,
        day_load: dict,
        court_load: dict,
        player_day_set: dict,
        hour_load: dict | None = None,
        weekday_load: dict | None = None,
        note: str | None = None,
    ) -> None:
        p1_id = match.pair_1.id
        p2_id = match.pair_2.id
        player_ids = [
            match.pair_1.player_1.id, match.pair_1.player_2.id,
            match.pair_2.player_1.id, match.pair_2.player_2.id,
        ]
        match.suggested_date       = best.date
        match.suggested_start_time = best.start_time
        match.suggested_end_time   = best.end_time
        match.court                = best.court
        match.status               = MatchStatus.SCHEDULED
        match.conflict_reason      = note

        occupied_slots.add((best.court.id, best.date, best.start_time))
        pair_schedule[p1_id].append((best.date, best.start_time, best.end_time, best.court.id))
        pair_schedule[p2_id].append((best.date, best.start_time, best.end_time, best.court.id))
        pair_weekly_count[p1_id][self._week_num(best.date)] += 1
        pair_weekly_count[p2_id][self._week_num(best.date)] += 1
        for pid in player_ids:
            player_day_set[pid].add(best.date)
        day_load[best.date]        += 1
        court_load[best.court.id]  += 1
        if hour_load is not None:
            hb = self._hour_bucket(best.start_time)
            hour_load[hb] = hour_load.get(hb, 0) + 1
        if weekday_load is not None:
            wd = best.date.weekday()
            weekday_load[wd] = weekday_load.get(wd, 0) + 1

    # -------------------------------------------------------------------
    # Bucle principal con relajación progresiva
    # -------------------------------------------------------------------

    def schedule(self, matches: list[Match]) -> ScheduleResult:
        """
        Asigna horarios en hasta 3 pasadas con relajación progresiva:
          Pasada 1 — todas las restricciones activas
          Pasada 2 — relaja separación mínima entre partidos
          Pasada 3 — relaja también el cruce de jugadores entre rankings

        Restricciones que NUNCA se relajan (reglas duras):
          · Disponibilidad declarada de la pareja (días/horas en Observaciones)
          · Máximo 1 partido por pareja y semana
          · No hay partidos en sábado ni domingo (filtrado antes de generar slots)

        Si no hay hueco que respete estas reglas, el partido queda como CONFLICTO.
        Los partidos asignados en pasadas 2-3 quedan marcados con una nota
        explicativa para que el revisor los identifique en la tabla.
        """
        slots = build_availability_slots(
            courts=self.phase.courts,
            phase=self.phase,
            bookings=self.phase.bookings,
        )
        slots.sort(key=lambda s: (s.date, s.start_time, s.court.name))

        # ── Ordenar partidos
        # 1. Mezcla aleatoria (determinista con seed) para equidad entre grupos
        shuffled = list(matches)
        self._rng.shuffle(shuffled)
        group_order = list(dict.fromkeys(m.group_id for m in shuffled))
        shuffled.sort(key=lambda m: group_order.index(m.group_id))
        # 2. Dentro de cada grupo: primero los partidos más difíciles de asignar
        shuffled.sort(
            key=lambda m: (group_order.index(m.group_id),
                           -self._constraint_difficulty(m))
        )

        # ── Estado compartido
        occupied_slots:     set[tuple[str, date, time]]            = set()
        pair_schedule:      dict[str, list[tuple]]                 = defaultdict(list)
        pair_weekly_count:  dict[str, dict[int, int]]              = defaultdict(lambda: defaultdict(int))
        day_load:           dict[date, int]                        = defaultdict(int)
        court_load:         dict[str, int]                         = defaultdict(int)
        player_day_set:     dict[str, set[date]]                   = defaultdict(set)
        # Cargas globales para reparto de horarios y días de semana
        hour_load:    dict[int, int] = {}
        weekday_load: dict[int, int] = {}

        scheduled:        list[Match]    = []
        conflict_details: list[Conflict] = []

        # ── Separar partidos de asignación manual
        manual_pending:   list[Match]    = []
        auto_matches:     list[Match]    = []
        for m in shuffled:
            if getattr(m.pair_1, "manual_only", False) or getattr(m.pair_2, "manual_only", False):
                m.status = MatchStatus.PENDING
                m.conflict_reason = "📋 Asignación manual — ver Observaciones"
                manual_pending.append(m)
            else:
                auto_matches.append(m)

        # ── Pasadas con relajación progresiva
        # (relax_min_days, relax_max_week, relax_availability, relax_cross_player, nota)
        # · relax_availability = SIEMPRE False (disponibilidad es restricción dura)
        # · relax_max_week     = SIEMPRE False (máx 1 partido/semana es restricción dura)
        PASSES = [
            (False, False, False, False, None),
            (True,  False, False, False, "⚠️ Sep. mínima relajada"),
            (True,  False, False, True,  "⚠️ Cruce jugadores relajado"),
        ]

        remaining = list(auto_matches)
        for relax_min, relax_week, relax_avail, relax_cross, note in PASSES:
            still_remaining: list[Match] = []
            for match in remaining:
                best = self._find_best_slot(
                    match, slots, occupied_slots, pair_schedule,
                    pair_weekly_count, day_load, court_load, player_day_set,
                    hour_load, weekday_load,
                    relax_min_days=relax_min,
                    relax_max_week=relax_week,
                    relax_availability=relax_avail,
                    relax_cross_player=relax_cross,
                )
                if best is not None:
                    self._apply_assignment(
                        match, best, occupied_slots, pair_schedule,
                        pair_weekly_count, day_load, court_load, player_day_set,
                        hour_load, weekday_load,
                        note=note,
                    )
                    scheduled.append(match)
                else:
                    still_remaining.append(match)
            remaining = still_remaining
            if not remaining:
                break

        # ---- Conflictos reales (sin solución respetando disponibilidades) ----
        conflicts: list[Match] = []
        for match in remaining:
            match.status = MatchStatus.CONFLICT
            match.conflict_reason = (
                "Sin huecos compatibles con la disponibilidad de ambas parejas. "
                "Revisa las Observaciones o amplía el rango de fechas."
            )
            conflicts.append(match)
            conflict_details.append(
                Conflict.model_construct(
                    match_id=match.id,
                    match_label=match.label,
                    reason=match.conflict_reason,
                    pair_ids_involved=[match.pair_1.id, match.pair_2.id],
                )
            )

        # Los partidos manuales se añaden a conflicts para que aparezcan
        # en la tabla con estado PENDING (el usuario los gestiona a mano)
        conflicts.extend(manual_pending)

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
