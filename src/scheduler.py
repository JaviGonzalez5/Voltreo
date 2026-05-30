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
import re
import unicodedata

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


def _day_end_dt(d: date, end_t: time) -> datetime:
    """
    Datetime del FIN del día de juego. Una hora de cierre de 00:00 se interpreta
    como medianoche = fin del día (24:00), es decir, las 00:00 del día siguiente.
    Así un club abierto hasta las 00:00 permite partidos hasta medianoche.
    """
    if end_t == time(0, 0):
        return datetime.combine(d, time(0, 0)) + timedelta(days=1)
    return datetime.combine(d, end_t)


def _overlaps(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    """True si los dos intervalos se solapan (excluyendo contacto en los extremos)."""
    return s1 < e2 and s2 < e1


# Granularidad de inicio de slots: cada 30 min → 17:00, 17:30, 18:00, 18:30, …
_SLOT_STEP = timedelta(minutes=30)


def _player_natural_key(player) -> str:
    """
    Clave normalizada para identificar al mismo jugador físico en distintos grupos.

    El mismo jugador puede aparecer con UUIDs diferentes en cada nivel de ranking.
    Esta función devuelve un nombre completo en minúsculas y sin acentos,
    lo que permite detectar colisiones cross-ranking en `player_day_set`.
    Fallback al UUID si el nombre está vacío.
    """
    raw = f"{player.name} {getattr(player, 'surname', '')}".strip().lower()
    # Quitar acentos para matching robusto (García == Garcia)
    nfkd = unicodedata.normalize("NFKD", raw)
    key = "".join(c for c in nfkd if not unicodedata.combining(c))
    return key or player.id


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
    pf_patterns: "frozenset[tuple[int, time]] | None" = None,
) -> list[AvailabilitySlot]:
    """
    Genera todos los huecos disponibles en cada pista para cada día de la fase.

    Los slots se generan con granularidad de 30 minutos (_SLOT_STEP), de modo que
    un partido puede comenzar a las 17:00, 17:30, 18:00, 18:30, 19:00, 19:30, …
    Cada slot tiene duración match_duration_minutes (p.ej. 90 min).

    Las reservas se asocian a pistas por ID, nombre exacto o número del nombre
    para cubrir el caso en que Syltek usa 'Padel N' y el scheduler 'Pista N'.

    pf_patterns: conjunto de (weekday, start_time) de pistas fijas conocidas.
    Los slots que coincidan con una PF se generan aunque haya una reserva en
    Syltek — esa reserva ES la reserva periódica de la PF y no debe bloquear
    el slot de ranking.
    """
    slots: list[AvailabilitySlot] = []
    duration = timedelta(minutes=phase.match_duration_minutes)
    current = phase.start_date

    # Precompute: for each active court, collect its bookings grouped by date.
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

        wd = current.weekday()
        for court in active_courts:
            day_bookings = court_day_bookings[court.id].get(current, [])

            slot_start = _dt(current, phase.day_start_time)
            day_end    = _day_end_dt(current, phase.day_end_time)

            # Avanzar de 30 en 30 min; cada slot dura match_duration_minutes
            while slot_start + duration <= day_end:
                slot_end = slot_start + duration

                # Slots de pista fija: no bloquear aunque haya reserva Syltek
                is_pf_slot = (
                    pf_patterns is not None
                    and (wd, slot_start.time()) in pf_patterns
                )
                if is_pf_slot:
                    blocked = False
                else:
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
                slot_start += _SLOT_STEP  # granularidad 30 min

            # ── Inyectar slots de Pista Fija fuera de la rejilla de 30 min.
            # Si una PF cae a las 20:45 (con day_start 16:00 la rejilla no la
            # genera), creamos el slot exacto para que el partido pueda asignarse.
            if pf_patterns:
                grid_times = {
                    (phase.day_start_time.hour * 60 + phase.day_start_time.minute) + 30 * k
                    for k in range(0, 48)
                }
                for pf_wd, pf_t in pf_patterns:
                    if pf_wd != wd:
                        continue
                    pf_min = pf_t.hour * 60 + pf_t.minute
                    if pf_min in grid_times:
                        continue  # ya generado por la rejilla
                    pf_start = _dt(current, pf_t)
                    pf_end   = pf_start + duration
                    if pf_end > day_end:
                        continue
                    # PF nunca se bloquea por reservas Syltek (esa ES su reserva)
                    slots.append(
                        AvailabilitySlot(
                            court=court,
                            date=current,
                            start_time=pf_t,
                            end_time=pf_end.time(),
                        )
                    )

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

        # Leer pesos con fallback defensivo:
        # model_construct() puede omitir campos si la fase viene de session state antiguo.
        same_hour_w    = getattr(w, "same_hour_penalty",    10.0)
        same_wd_w      = getattr(w, "same_weekday_penalty",  6.0)
        same_court_w   = getattr(w, "same_court_penalty",    2.0)
        day_load_w     = getattr(w, "day_load_penalty",      1.5)
        court_load_w   = getattr(w, "court_load_penalty",    1.0)
        early_day_w    = getattr(w, "early_day_bonus",       0.5)
        global_hour_w  = getattr(w, "global_hour_penalty",   5.0)
        global_wd_w    = getattr(w, "global_weekday_penalty", 4.0)

        # Penalizaciones por repetición para AMBAS parejas
        for pid in (p1_id, p2_id):
            for ps_date, ps_start, _ps_end, ps_court in pair_schedule[pid]:
                if self._hour_bucket(ps_start) == hour_b:
                    score += same_hour_w
                if ps_date.weekday() == weekday:
                    score += same_wd_w
                if ps_court == court_id:
                    score += same_court_w

        # Penalización por carga del día y de la pista (preferimos repartir)
        score += day_load.get(slot.date, 0) * day_load_w
        score += court_load.get(court_id, 0) * court_load_w

        # Penalizaciones GLOBALES: evitan que todos los partidos se amontonen
        # en la misma hora/día aunque sea la primera vez de cada pareja.
        if hour_load is not None:
            score += hour_load.get(hour_b, 0) * global_hour_w
        if weekday_load is not None:
            score += weekday_load.get(weekday, 0) * global_wd_w

        # Bonus leve por programar pronto en la fase (resta puntuación)
        days_offset = (slot.date - self.phase.start_date).days
        score -= max(0, 30 - days_offset) * (early_day_w / 30.0)

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

        # Penalizar horas tardías del día.
        # Hace que el scheduler prefiera la primera hora disponible de la pareja
        # en lugar de repartir uniformemente hasta las 22:30.
        # Escala lineal: 0 en day_start_time → late_hour_penalty * 12 en day_end_time.
        late_penalty = getattr(w, "late_hour_penalty", 2.5)
        if late_penalty > 0:
            day_start_min = self.phase.day_start_time.hour * 60 + self.phase.day_start_time.minute
            # Cierre a las 00:00 = medianoche (24:00) → 1440 min
            day_end_min   = (self.phase.day_end_time.hour * 60 + self.phase.day_end_time.minute) or 1440
            slot_min      = slot.start_time.hour * 60 + slot.start_time.minute
            hour_range    = max(day_end_min - day_start_min, 1)
            hour_fraction = (slot_min - day_start_min) / hour_range  # [0.0 … 1.0]
            score += hour_fraction * late_penalty * 12.0

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
            # Pista fija: el slot exacto (día+hora) es crítico → máxima prioridad
            if (getattr(pair, "preferred_weekday", None) is not None
                    and getattr(pair, "preferred_time", None) is not None):
                score += 80
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
        · N viene de BalanceWeights.top_candidates_pool (por defecto 4).
        """
        p1_id = match.pair_1.id
        p2_id = match.pair_2.id
        # Usar clave por nombre normalizado para detectar el mismo jugador
        # en distintos grupos (mismo jugador físico → misma clave cross-ranking).
        player_keys = [
            _player_natural_key(match.pair_1.player_1),
            _player_natural_key(match.pair_1.player_2),
            _player_natural_key(match.pair_2.player_1),
            _player_natural_key(match.pair_2.player_2),
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
                if any(d in player_day_set[pk] for pk in player_keys):
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

        # ── PISTA FIJA (restricción casi-dura) ──────────────────────────
        # Si alguna pareja tiene pista fija (preferred_weekday + preferred_time)
        # y existe un slot candidato que coincide EXACTAMENTE con ese día+hora
        # (y por tanto ya ha pasado todas las restricciones físicas y de
        # disponibilidad de AMBAS parejas), el partido DEBE ir ahí.
        # Esto evita que el bonus suave de PF sea superado por late_hour_penalty
        # u otras penalizaciones, o que la aleatoriedad del pool lo descarte.
        pf_pairs = [
            p for p in (match.pair_1, match.pair_2)
            if getattr(p, "preferred_weekday", None) is not None
            and getattr(p, "preferred_time", None) is not None
        ]
        pf_restricted = False
        if pf_pairs:
            def _pf_match(slot, pair) -> bool:
                return (slot.date.weekday() == pair.preferred_weekday
                        and slot.start_time == pair.preferred_time)

            # 1) Ideal: slot que cumple la PF de TODAS las parejas (misma franja).
            all_pf = [s for s in candidates if all(_pf_match(s, p) for p in pf_pairs)]
            if all_pf:
                candidates = all_pf
                pf_restricted = True
            else:
                # 2) PF en conflicto (franjas distintas): el partido SOLO puede
                #    estar en una de las dos franjas fijas → restringir a los slots
                #    que cumplan la PF de ALGUNA pareja. Así nunca se asigna a un
                #    hueco arbitrario cuando existe la franja fija de un rival.
                any_pf = [s for s in candidates if any(_pf_match(s, p) for p in pf_pairs)]
                if any_pf:
                    candidates = any_pf
                    pf_restricted = True

        # ── Ordenar por score y elegir aleatoriamente entre los top-N
        def _score(s):
            return self._slot_score(
                s, p1_id, p2_id, pair_schedule, day_load, court_load,
                hour_load=hour_load, weekday_load=weekday_load,
                pair_1=match.pair_1, pair_2=match.pair_2,
            )

        candidates.sort(key=_score)
        # Con pista fija: elegir el mejor de forma DETERMINISTA (sin randomización),
        # garantizando que el partido cae en su franja fija siempre que sea posible.
        if pf_restricted:
            return candidates[0]
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
        player_keys = [
            _player_natural_key(match.pair_1.player_1),
            _player_natural_key(match.pair_1.player_2),
            _player_natural_key(match.pair_2.player_1),
            _player_natural_key(match.pair_2.player_2),
        ]
        match.suggested_date       = best.date
        match.suggested_start_time = best.start_time
        match.suggested_end_time   = best.end_time
        match.court                = best.court
        match.status               = MatchStatus.SCHEDULED
        match.conflict_reason      = note

        # Marcar todos los sub-slots de 30 min que ocupa este partido en la pista,
        # para que ningún otro partido se solape con él en la misma pista.
        _t = _dt(best.date, best.start_time)
        _end = _dt(best.date, best.end_time)
        while _t < _end:
            occupied_slots.add((best.court.id, best.date, _t.time()))
            _t += _SLOT_STEP
        pair_schedule[p1_id].append((best.date, best.start_time, best.end_time, best.court.id))
        pair_schedule[p2_id].append((best.date, best.start_time, best.end_time, best.court.id))
        pair_weekly_count[p1_id][self._week_num(best.date)] += 1
        pair_weekly_count[p2_id][self._week_num(best.date)] += 1
        for pk in player_keys:
            player_day_set[pk].add(best.date)
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
        # ── Franjas de Pistas Fijas: (weekday, time) de todas las parejas con PF.
        # Estas franjas se incluyen en los slots disponibles aunque haya una reserva
        # de Syltek — esa reserva ES la reserva periódica de la PF, no un bloqueo.
        # La asignación concreta se gestiona por scoring + prioridad:
        #   · _constraint_difficulty: partidos con PF se procesan primero.
        #   · preferred_slot_bonus: puntuación fuerte hacia el slot exacto.
        # Si la otra pareja no tiene disponibilidad en ese slot, el scheduler
        # asignará el partido en otro hueco sin forzar la PF.
        pf_patterns: set[tuple[int, time]] = set()
        for g in self.phase.groups:
            for p in g.pairs:
                pw = getattr(p, "preferred_weekday", None)
                pt = getattr(p, "preferred_time", None)
                if pw is not None and pt is not None:
                    pf_patterns.add((pw, pt))

        slots = build_availability_slots(
            courts=self.phase.courts,
            phase=self.phase,
            bookings=self.phase.bookings,
            pf_patterns=frozenset(pf_patterns) if pf_patterns else None,
        )
        slots.sort(key=lambda s: (s.date, s.start_time, s.court.name))

        # ── Ordenar partidos
        # Mezcla aleatoria (determinista con seed) para equidad entre grupos,
        # luego ordena: primero por grupo, después por dificultad descendente
        # (los partidos más difíciles de encajar se procesan antes para que
        # tengan más opciones de slot disponibles).
        # ── Ordenar partidos con equidad entre grupos.
        #
        # En lugar de procesar todos los partidos de un grupo antes de pasar
        # al siguiente (lo que deja a los últimos grupos con los peores huecos),
        # se intercalan los grupos: cada grupo cede un partido por turno.
        #
        # Dentro de cada grupo los partidos se ordenan por dificultad descendente
        # (los más difíciles de encajar primero) para maximizar la tasa de éxito.
        # El orden entre grupos es aleatorio (determinista con la seed) para que
        # ningún grupo tenga ventaja sistemática sobre otro.
        shuffled = list(matches)
        self._rng.shuffle(shuffled)

        # Agrupar por group_id conservando el orden aleatorio de los grupos
        _group_buckets: dict[str, list[Match]] = {}
        for m in shuffled:
            _group_buckets.setdefault(m.group_id, []).append(m)

        # Ordenar dentro de cada grupo: más difíciles primero
        for bucket in _group_buckets.values():
            bucket.sort(key=lambda m: -self._constraint_difficulty(m))

        # Intercalar: un partido por grupo en cada ronda (round-robin entre grupos)
        _group_lists = list(_group_buckets.values())
        interleaved: list[Match] = []
        max_len = max((len(g) for g in _group_lists), default=0)
        for i in range(max_len):
            for g_list in _group_lists:
                if i < len(g_list):
                    interleaved.append(g_list[i])

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
        for m in interleaved:
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
