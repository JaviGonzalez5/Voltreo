"""
Planificador de horarios para torneos.

Diferencias clave respecto al scheduler de ranking:
  · Todos los partidos se juegan en el mismo rango de días (normalmente 1-2).
  · No hay límite semanal ni días de separación: el límite es el descanso
    mínimo entre partidos consecutivos del mismo equipo (rest_between_matches_min).
  · Los partidos de cuadro (rondas post-grupos) se programan DESPUÉS de que
    terminen todos los partidos de la ronda anterior.
  · Se usan pistas en paralelo para compactar el torneo al máximo.

Algoritmo:
  1. Agrupa los partidos por ronda (phase).
  2. Para cada ronda (en orden):
       a. La ronda empieza como máximo en start_of_day, pero no antes
          del fin de la ronda anterior + descanso.
       b. Asigna cada partido al hueco más temprano disponible ENTRE TODAS las pistas:
          · Una pista solo tiene un partido a la vez.
          · El mismo equipo necesita >= rest_between_matches_min de margen.
       c. Si un partido no cabe en ningún hueco del día, prueba el día siguiente.
  3. Si no cabe en todo el rango de fechas → CONFLICT.
"""

from collections import defaultdict
from datetime import date, time, datetime, timedelta
from typing import Optional

from .tournament_models import (
    TournamentConfig,
    TournamentMatch,
    TournamentCourt,
    TMatchStatus,
    MatchRound,
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _days_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# Estado del scheduler
# ---------------------------------------------------------------------------

class _CourtTimeline:
    """Registra cuándo está libre una pista en un día concreto."""

    def __init__(self):
        self._free: dict[date, datetime] = {}   # {date: earliest_free}

    def free_at(self, d: date, day_start: time) -> datetime:
        return self._free.get(d, _dt(d, day_start))

    def mark_occupied(self, d: date, end: datetime) -> None:
        if d not in self._free or end > self._free[d]:
            self._free[d] = end


class _PairTimeline:
    """Registra el fin del último partido asignado a cada pareja."""

    def __init__(self, rest_minutes: int):
        self._rest   = timedelta(minutes=rest_minutes)
        self._last:  dict[str, datetime] = {}

    def available_from(self, pair_id: str) -> Optional[datetime]:
        last = self._last.get(pair_id)
        return (last + self._rest) if last else None

    def record(self, pair_id: str, end: datetime) -> None:
        if pair_id not in self._last or end > self._last[pair_id]:
            self._last[pair_id] = end


# ---------------------------------------------------------------------------
# Planificador principal
# ---------------------------------------------------------------------------

def schedule_tournament(config: TournamentConfig) -> TournamentConfig:
    """
    Asigna fecha, hora y pista a cada TournamentMatch en config.matches.
    Modifica config.matches in-place y devuelve config.
    """
    if not config.matches or not config.courts:
        return config

    duration     = timedelta(minutes=config.match_duration_minutes)
    active_courts = [c for c in config.courts if c.active]
    if not active_courts:
        return config

    all_days  = _days_between(config.start_date, config.end_date)
    day_start = config.day_start_time
    day_end   = config.day_end_time

    # ── Agrupar por ronda y ordenar
    rounds_ordered: list[MatchRound] = sorted(
        set(m.round for m in config.matches),
        key=lambda r: r.order,
    )
    matches_by_round: dict[MatchRound, list[TournamentMatch]] = defaultdict(list)
    for m in config.matches:
        matches_by_round[m.round].append(m)

    # ── Estado compartido
    court_tls  = {c.id: _CourtTimeline() for c in active_courts}
    pair_tl    = _PairTimeline(config.rest_between_matches_min)
    prev_round_end: Optional[datetime] = None

    for rnd in rounds_ordered:
        matches = matches_by_round[rnd]

        # El cuadro no empieza antes de que acaben los grupos
        rnd_earliest: Optional[datetime] = None
        if rnd != MatchRound.GROUP and prev_round_end is not None:
            rnd_earliest = prev_round_end + timedelta(minutes=config.rest_between_matches_min)

        rnd_latest_end: Optional[datetime] = None

        for match in matches:
            slot = _find_best_slot(
                match        = match,
                active_courts= active_courts,
                court_tls    = court_tls,
                pair_tl      = pair_tl,
                duration     = duration,
                all_days     = all_days,
                day_start    = day_start,
                day_end      = day_end,
                rnd_earliest = rnd_earliest,
            )

            if slot is None:
                match.status = TMatchStatus.CONFLICT
                match.conflict_reason = (
                    "Sin hueco disponible. Amplía el rango de fechas, "
                    "añade más pistas o reduce la duración de los partidos."
                )
            else:
                s_start, s_end, court = slot
                match.match_date = s_start.date()
                match.start_time = s_start.time()
                match.end_time   = s_end.time()
                match.court      = court
                match.status     = TMatchStatus.SCHEDULED

                court_tls[court.id].mark_occupied(match.match_date, s_end)
                if match.pair_1:
                    pair_tl.record(match.pair_1.id, s_end)
                if match.pair_2:
                    pair_tl.record(match.pair_2.id, s_end)

                if rnd_latest_end is None or s_end > rnd_latest_end:
                    rnd_latest_end = s_end

        if rnd_latest_end is not None:
            prev_round_end = rnd_latest_end

    return config


# ---------------------------------------------------------------------------
# Búsqueda del mejor hueco (más temprano entre todas las pistas)
# ---------------------------------------------------------------------------

def _find_best_slot(
    match:         TournamentMatch,
    active_courts: list[TournamentCourt],
    court_tls:     dict[str, _CourtTimeline],
    pair_tl:       _PairTimeline,
    duration:      timedelta,
    all_days:      list[date],
    day_start:     time,
    day_end:       time,
    rnd_earliest:  Optional[datetime],
) -> Optional[tuple[datetime, datetime, TournamentCourt]]:
    """
    Devuelve (start, end, court) del hueco más temprano disponible
    entre todas las pistas y todos los días del torneo.

    La función COMPARA todas las pistas en cada día y elige la que
    permita el inicio más temprano — esto garantiza el uso en paralelo.
    """
    p1_id = match.pair_1.id if match.pair_1 else None
    p2_id = match.pair_2.id if match.pair_2 else None

    p1_avail = pair_tl.available_from(p1_id) if p1_id else None
    p2_avail = pair_tl.available_from(p2_id) if p2_id else None

    for d in all_days:
        day_start_dt = _dt(d, day_start)
        day_end_dt   = _dt(d, day_end)

        # Encontrar la pista que permita el inicio más temprano hoy
        best_start:  Optional[datetime]       = None
        best_end:    Optional[datetime]       = None
        best_court:  Optional[TournamentCourt] = None

        for court in active_courts:
            ct       = court_tls[court.id]
            ct_free  = ct.free_at(d, day_start)

            # La pista podría estar libre desde un día anterior (no importa,
            # lo que cuenta es cuándo está libre HOY).
            if ct_free.date() > d:
                continue   # pista ocupada hasta mañana o después

            # Hora mínima de inicio teniendo en cuenta todas las restricciones
            earliest_start = ct_free if ct_free.date() == d else day_start_dt

            if rnd_earliest is not None:
                if rnd_earliest.date() > d:
                    continue  # Esta ronda no puede empezar hoy
                earliest_start = max(earliest_start, rnd_earliest)

            if p1_avail is not None:
                if p1_avail.date() > d:
                    continue  # Pareja 1 aún no ha descansado para hoy
                earliest_start = max(earliest_start, p1_avail)

            if p2_avail is not None:
                if p2_avail.date() > d:
                    continue
                earliest_start = max(earliest_start, p2_avail)

            # Asegurar que no cae antes del inicio del día
            slot_start = max(earliest_start, day_start_dt)
            slot_end   = slot_start + duration

            if slot_end > day_end_dt:
                continue   # No cabe antes del fin del día

            # ¿Es este el slot más temprano encontrado hasta ahora?
            if best_start is None or slot_start < best_start:
                best_start = slot_start
                best_end   = slot_end
                best_court = court

        if best_court is not None:
            return best_start, best_end, best_court

    return None


# ---------------------------------------------------------------------------
# Estadísticas post-planificación
# ---------------------------------------------------------------------------

def tournament_schedule_summary(config: TournamentConfig) -> dict:
    """Estadísticas del calendario generado."""
    scheduled = [m for m in config.matches if m.status == TMatchStatus.SCHEDULED]
    conflicts  = [m for m in config.matches if m.status == TMatchStatus.CONFLICT]

    if not scheduled:
        return {
            "scheduled":   0,
            "conflicts":   len(conflicts),
            "first_match": None,
            "last_match":  None,
            "courts_used": [],
        }

    from datetime import datetime as _dtt
    first = min(scheduled, key=lambda m: _dtt.combine(m.match_date, m.start_time))
    last  = max(scheduled, key=lambda m: _dtt.combine(m.match_date, m.end_time))

    return {
        "scheduled":   len(scheduled),
        "conflicts":   len(conflicts),
        "first_match": f"{first.match_date.strftime('%d/%m/%Y')} {first.start_time.strftime('%H:%M')}",
        "last_match":  f"{last.match_date.strftime('%d/%m/%Y')} {last.end_time.strftime('%H:%M')}",
        "courts_used": list({m.court.name for m in scheduled if m.court}),
    }
