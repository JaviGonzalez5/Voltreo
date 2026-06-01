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

import unicodedata
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
# Identidad de jugador (para detectar el mismo jugador en distintas categorías)
# ---------------------------------------------------------------------------

def _player_key(player) -> str:
    """
    Clave normalizada del jugador físico: nombre completo en minúsculas y sin
    acentos. Permite detectar que el mismo jugador participa en varias
    categorías (ej. Masculino y Mixto) aunque sea en parejas distintas, para
    que no se le asignen dos partidos simultáneos.
    """
    if player is None:
        return ""
    raw = f"{getattr(player, 'name', '')} {getattr(player, 'surname', '')}".strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    key = "".join(c for c in nfkd if not unicodedata.combining(c))
    return key or getattr(player, "id", "")


def _match_player_keys(match: TournamentMatch) -> list[str]:
    """Claves de los hasta 4 jugadores de un partido (vacío si pareja TBD)."""
    keys: list[str] = []
    for pair in (match.pair_1, match.pair_2):
        if pair is None:
            continue
        for pl in (getattr(pair, "player_1", None), getattr(pair, "player_2", None)):
            k = _player_key(pl)
            if k:
                keys.append(k)
    return keys


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _day_end_dt(d: date, end_t: time, start_t: time = time(0, 0)) -> datetime:
    """
    Fin del día de juego. Si la hora de fin es 00:00 o es anterior/igual a la de
    inicio (ej. inicio 19:00, fin 00:30), se interpreta como de madrugada del
    día siguiente.
    """
    if end_t == time(0, 0) or end_t <= start_t:
        return datetime.combine(d, end_t) + timedelta(days=1)
    return datetime.combine(d, end_t)


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
    """Registra el instante en que una pista queda libre (monotónico).

    Un único datetime por pista funciona para sesiones consecutivas, sesiones
    que pasan de medianoche y torneos de varios días, porque siempre se acota
    al inicio de la jornada correspondiente al planificar.
    """

    def __init__(self):
        self._free: Optional[datetime] = None

    def free_from(self) -> Optional[datetime]:
        return self._free

    def mark_occupied(self, end: datetime) -> None:
        if self._free is None or end > self._free:
            self._free = end


class _PlayerTimeline:
    """
    Registra el fin del último partido de cada JUGADOR (no de cada pareja).

    Así, un jugador que compite en varias categorías queda bloqueado en todas
    ellas: su siguiente partido (en cualquier categoría) no puede empezar antes
    de que termine el anterior + descanso. Evita partidos simultáneos del mismo
    jugador físico.
    """

    def __init__(self, rest_minutes: int):
        self._rest  = timedelta(minutes=rest_minutes)
        self._last: dict[str, datetime] = {}

    def available_from(self, player_keys: list[str]) -> Optional[datetime]:
        """Momento más temprano en que TODOS los jugadores del partido están libres."""
        latest: Optional[datetime] = None
        for k in player_keys:
            last = self._last.get(k)
            if last is not None:
                cand = last + self._rest
                if latest is None or cand > latest:
                    latest = cand
        return latest

    def record(self, player_keys: list[str], end: datetime) -> None:
        for k in player_keys:
            if k not in self._last or end > self._last[k]:
                self._last[k] = end


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

    # ── Tandas de juego: agrupar divisiones por nº de tanda (1, 2, 3…)
    _waves_cfg = dict(getattr(config, "division_waves", {}) or {})

    def _wave_of(m: TournamentMatch) -> int:
        return int(_waves_cfg.get(m.division, 1)) if m.division else 1

    _wave_numbers = sorted({_wave_of(m) for m in config.matches})

    # ── Estado compartido (persiste entre tandas: pistas y jugadores)
    court_tls  = {c.id: _CourtTimeline() for c in active_courts}
    player_tl  = _PlayerTimeline(config.rest_between_matches_min)

    # Fin de la tanda anterior: la siguiente tanda no empieza antes
    wave_prev_end: Optional[datetime] = None

    for _wave in _wave_numbers:
        wave_matches = [m for m in config.matches if _wave_of(m) == _wave]

        # ── Agrupar por ronda y ordenar (dentro de la tanda)
        rounds_ordered: list[MatchRound] = sorted(
            set(m.round for m in wave_matches),
            key=lambda r: r.order,
        )
        matches_by_round: dict[MatchRound, list[TournamentMatch]] = defaultdict(list)
        for m in wave_matches:
            matches_by_round[m.round].append(m)

        prev_round_end: Optional[datetime] = None
        wave_latest_end: Optional[datetime] = None

        for rnd in rounds_ordered:
            matches = matches_by_round[rnd]

            # Suelo temporal: el cuadro tras los grupos, y la tanda tras la anterior
            rnd_earliest: Optional[datetime] = wave_prev_end
            if rnd != MatchRound.GROUP and prev_round_end is not None:
                _after_groups = prev_round_end + timedelta(minutes=config.rest_between_matches_min)
                rnd_earliest = max(rnd_earliest, _after_groups) if rnd_earliest else _after_groups

            rnd_latest_end: Optional[datetime] = None

            for match in matches:
                slot = _find_best_slot(
                    match        = match,
                    active_courts= active_courts,
                    court_tls    = court_tls,
                    player_tl    = player_tl,
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
                    # Día de la sesión: si el partido empieza de madrugada
                    # (antes de la hora de inicio), pertenece a la noche anterior.
                    _session_day = s_start.date()
                    if s_start.time() < day_start:
                        _session_day = s_start.date() - timedelta(days=1)
                    match.match_date = _session_day
                    match.start_time = s_start.time()
                    match.end_time   = s_end.time()
                    match.court      = court
                    match.status     = TMatchStatus.SCHEDULED

                    court_tls[court.id].mark_occupied(s_end)
                    player_tl.record(_match_player_keys(match), s_end)

                    if rnd_latest_end is None or s_end > rnd_latest_end:
                        rnd_latest_end = s_end
                    if wave_latest_end is None or s_end > wave_latest_end:
                        wave_latest_end = s_end

            if rnd_latest_end is not None:
                prev_round_end = rnd_latest_end

        # La próxima tanda no empieza antes de que acabe esta
        if wave_latest_end is not None:
            _next = wave_latest_end + timedelta(minutes=config.rest_between_matches_min)
            wave_prev_end = max(wave_prev_end, _next) if wave_prev_end else _next

    return config


# ---------------------------------------------------------------------------
# Búsqueda del mejor hueco (más temprano entre todas las pistas)
# ---------------------------------------------------------------------------

def _find_best_slot(
    match:         TournamentMatch,
    active_courts: list[TournamentCourt],
    court_tls:     dict[str, _CourtTimeline],
    player_tl:     _PlayerTimeline,
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

    Tiene en cuenta a TODOS los jugadores del partido: si alguno juega en otra
    categoría, no puede tener dos partidos a la vez.
    """
    # Momento más temprano en que todos los jugadores del partido están libres
    players_avail = player_tl.available_from(_match_player_keys(match))

    for d in all_days:
        day_start_dt = _dt(d, day_start)
        day_end_dt   = _day_end_dt(d, day_end, day_start)

        # Encontrar la pista que permita el inicio más temprano hoy
        best_start:  Optional[datetime]       = None
        best_end:    Optional[datetime]       = None
        best_court:  Optional[TournamentCourt] = None

        for court in active_courts:
            ct       = court_tls[court.id]
            ct_free  = ct.free_from()

            # Inicio más temprano en ESTA jornada (acotado al inicio del día)
            earliest_start = day_start_dt if ct_free is None else max(ct_free, day_start_dt)

            if rnd_earliest is not None:
                earliest_start = max(earliest_start, rnd_earliest)
            if players_avail is not None:
                earliest_start = max(earliest_start, players_avail)

            slot_start = earliest_start
            slot_end   = slot_start + duration

            if slot_end > day_end_dt:
                continue   # No cabe en la franja de esta jornada (incl. madrugada)

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

    def _real_start(m):
        dt = _dtt.combine(m.match_date, m.start_time)
        if m.start_time < config.day_start_time:
            dt += timedelta(days=1)
        return dt

    def _real_end(m):
        dt = _dtt.combine(m.match_date, m.end_time)
        if m.end_time <= m.start_time or m.end_time < config.day_start_time:
            dt += timedelta(days=1)
        return dt

    first = min(scheduled, key=_real_start)
    last  = max(scheduled, key=_real_end)

    return {
        "scheduled":   len(scheduled),
        "conflicts":   len(conflicts),
        "first_match": f"{first.match_date.strftime('%d/%m/%Y')} {first.start_time.strftime('%H:%M')}",
        "last_match":  f"{last.match_date.strftime('%d/%m/%Y')} {last.end_time.strftime('%H:%M')}",
        "courts_used": list({m.court.name for m in scheduled if m.court}),
    }
