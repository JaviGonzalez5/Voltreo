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


def _all_potential_player_keys(
    match: TournamentMatch,
    all_matches: "list[TournamentMatch]",
) -> list[str]:
    """
    Claves de jugadores de un partido, incluyendo los POTENCIALES si es TBD.

    Para partidos con pareja ya conocida devuelve lo mismo que _match_player_keys.
    Para partidos TBD (bracket cuadro aún no resuelto) sube recursivamente a la
    ronda anterior para encontrar todos los jugadores que podrían llegar a ese
    slot. Así el _PlayerTimeline bloquea correctamente a jugadores de Tanda 1
    que aún no saben si llegarán a la final, evitando solapamientos con Tanda 2.
    """
    direct = _match_player_keys(match)
    if direct:
        return direct

    # Partido TBD: buscar los partidos de la ronda anterior que alimentan este slot
    # "Ganador Cuartos 1" → partido de cuartos match_number=1 con misma división
    feeder_matches: list[TournamentMatch] = []
    for slot_num in (match.match_number * 2 - 1, match.match_number * 2):
        # Los partidos de la ronda anterior tienen round.order == match.round.order - 1
        for m in all_matches:
            if (m.division == match.division
                    and m.round.order == match.round.order - 1
                    and m.match_number == slot_num):
                feeder_matches.append(m)

    keys: list[str] = []
    for fm in feeder_matches:
        keys.extend(_all_potential_player_keys(fm, all_matches))
    return list(dict.fromkeys(keys))  # dedup preservando orden


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

    active_courts = [c for c in config.courts if c.active]
    if not active_courts:
        return config

    all_days  = _days_between(config.start_date, config.end_date)
    day_start = config.day_start_time
    day_end   = config.day_end_time

    # Helper: franja horaria real del día (sáb/dom puede tener franja distinta)
    def _day_hours(d: date) -> tuple[time, time]:
        if d.weekday() >= 5:  # 5=sábado, 6=domingo
            ws = getattr(config, "weekend_start_time", None)
            we = getattr(config, "weekend_end_time", None)
            return (ws or day_start), (we or day_end)
        return day_start, day_end

    # ── Modo distribución: pre-asignar partidos a días ──────────────────────
    # Cuando schedule_distribute_over_days=True (torneos de pádel multidia),
    # repartimos los partidos uniformemente entre todos los días del torneo
    # en lugar de comprimirlos al inicio. Cada partido solo puede empezar
    # en su día asignado o posterior, garantizando distribución uniforme.
    _distribute = bool(getattr(config, "schedule_distribute_over_days", False))
    _day_target: dict[str, date] = {}   # match_id → día mínimo asignado

    if _distribute and len(all_days) > 1:
        # Solo los partidos de grupos se distribuyen; cuadro/eliminatoria
        # sigue la lógica normal (depende de resultados de grupos).
        _group_matches = [m for m in config.matches if m.round == MatchRound.GROUP]
        _n = len(_group_matches)
        _nd = len(all_days)
        if _n > 0:
            # Cuántos partidos por día (distribución homogénea)
            _per_day = max(1, -(-_n // _nd))  # ceil division
            _day_idx = 0
            _placed_on_day = 0
            for _m in sorted(_group_matches, key=lambda m: (
                str(m.division or ""), m.round.order, m.match_number
            )):
                _day_target[_m.id] = all_days[min(_day_idx, _nd - 1)]
                _placed_on_day += 1
                if _placed_on_day >= _per_day and _day_idx < _nd - 1:
                    _day_idx += 1
                    _placed_on_day = 0

    # ── Tandas de juego: BARRERA DURA entre tandas, mezcla DENTRO de la tanda ─
    # Una tanda posterior (p.ej. Mixto = tanda 2) NO empieza hasta que TODA la
    # tanda anterior (Masculino + Femenino = tanda 1) haya terminado. Esto se
    # garantiza con dos mecanismos:
    #   · readiness: un partido de la tanda W no está "listo" mientras queden
    #     partidos sin programar de cualquier tanda < W.
    #   · earliest: además, no puede empezar antes del fin del ÚLTIMO partido de
    #     las tandas anteriores + descanso.
    # DENTRO de una tanda, el pase voraz mezcla las categorías (Masculino y
    # Femenino se intercalan, sin bloques) gracias al desempate por categoría
    # menos colocada. El _PlayerTimeline impide partidos simultáneos del mismo
    # jugador físico entre categorías o tandas.
    _waves_cfg = dict(getattr(config, "division_waves", {}) or {})

    def _wave_of(m: TournamentMatch) -> int:
        return int(_waves_cfg.get(m.division, 1)) if m.division else 1

    _wave_numbers = sorted({_wave_of(m) for m in config.matches})

    # ── Estado compartido (pistas y jugadores) ──────────────────────────────
    court_tls = {c.id: _CourtTimeline() for c in active_courts}
    player_tl = _PlayerTimeline(config.rest_between_matches_min)
    _rest_td  = timedelta(minutes=config.rest_between_matches_min)

    # Secuencia de rondas por división (para readiness y orden del cuadro)
    all_divisions = _ordered_wave_divisions(config, config.matches)
    div_rounds_list = {
        div: sorted(
            {m.round for m in config.matches if m.division == div},
            key=lambda r: r.order,
        )
        for div in all_divisions
    }

    # Estado de rondas por división: cuántos partidos completados / total
    completed_rounds: dict[tuple, int] = defaultdict(int)
    total_rounds:     dict[tuple, int] = defaultdict(int)
    # Estado por tanda: total, programados y fin más tardío (para la barrera dura)
    total_per_wave:     dict[int, int] = defaultdict(int)
    completed_per_wave: dict[int, int] = defaultdict(int)
    wave_end_latest:    dict[int, datetime] = {}
    for m in config.matches:
        total_rounds[(m.division, m.round)] += 1
        total_per_wave[_wave_of(m)] += 1

    def _prev_round_of(div, rnd):
        seq = div_rounds_list.get(div, [])
        idx = seq.index(rnd) if rnd in seq else -1
        return seq[idx - 1] if idx > 0 else None

    def _lower_waves_done(w: int) -> bool:
        """True si TODAS las tandas anteriores a w están 100% programadas."""
        return all(
            completed_per_wave[lw] == total_per_wave[lw]
            for lw in _wave_numbers if lw < w
        )

    def _wave_barrier_for(w: int) -> Optional[datetime]:
        """Fin del último partido de las tandas anteriores + descanso (o None)."""
        ends = [wave_end_latest[lw] for lw in _wave_numbers
                if lw < w and lw in wave_end_latest]
        return (max(ends) + _rest_td) if ends else None

    def _is_ready(m) -> bool:
        """Listo si (a) su ronda anterior en SU categoría está completada y
        (b) no queda nada por programar de tandas anteriores (barrera dura).

        Dentro de la misma tanda, las semis de Masculino pueden asignarse en
        cuanto terminan los grupos de Masculino, sin esperar a los de Femenino.
        """
        if not _lower_waves_done(_wave_of(m)):
            return False
        pr = _prev_round_of(m.division, m.round)
        if pr is None:
            return True
        _key = (m.division, pr)
        return completed_rounds[_key] == total_rounds[_key]

    div_round_latest: dict[tuple, datetime] = {}  # fin más tardío de cada (div, rnd)

    def _earliest_for(m) -> Optional[datetime]:
        """No empieza antes de (a) el fin de su ronda anterior (misma categoría)
        ni (b) el fin de TODAS las tandas anteriores, ambos + descanso."""
        base = _wave_barrier_for(_wave_of(m))
        pr = _prev_round_of(m.division, m.round)
        if pr is not None:
            pe = div_round_latest.get((m.division, pr))
            if pe is not None:
                after_pr = pe + _rest_td
                base = max(base, after_pr) if base else after_pr
        return base

    unscheduled = list(config.matches)
    _safety = len(unscheduled) * len(active_courts) + 5
    # Contadores para mezclar categorías y rotar grupos (solo como desempate).
    placed_per_div:        dict[object, int] = defaultdict(int)
    placed_per_group_name: dict[str, int]    = defaultdict(int)
    _gid_to_name = {g.id: g.name for g in config.groups}
    # Modo distribución: una pareja no puede jugar más de 1 partido por día.
    _player_day_busy: dict[str, set[date]] = defaultdict(set)

    while unscheduled and _safety > 0:
        _safety -= 1
        ready = [m for m in unscheduled if _is_ready(m)]
        if not ready:
            break

        # Calcular el hueco más temprano posible para cada partido listo
        candidates: list[tuple] = []   # (s_start, s_end, court, match)
        for m in ready:
            rnd_earliest = _earliest_for(m)
            # Modo distribución: si el partido tiene día asignado, no antes de ese día.
            if _distribute and m.id in _day_target:
                _assigned_day = _day_target[m.id]
                _day_dt = _dt(_assigned_day, _day_hours(_assigned_day)[0])
                rnd_earliest = max(rnd_earliest, _day_dt) if rnd_earliest else _day_dt
            # Modo distribución: días donde algún jugador ya tiene partido.
            _blocked_days: set[date] = set()
            if _distribute:
                for _pk in _all_potential_player_keys(m, config.matches):
                    _blocked_days.update(_player_day_busy.get(_pk, set()))
            duration = _duration_for_match(config, match=m)
            slot = _find_best_slot(
                match=m, active_courts=active_courts, court_tls=court_tls,
                player_tl=player_tl, duration=duration, all_days=all_days,
                day_start=day_start, day_end=day_end, rnd_earliest=rnd_earliest,
                all_matches=config.matches, blocked_days=_blocked_days,
                day_hours_fn=_day_hours,
            )
            if slot is not None:
                s_start, s_end, court = slot
                candidates.append((s_start, s_end, court, m))

        if not candidates:
            for m in ready:
                m.status = TMatchStatus.CONFLICT
                m.conflict_reason = (
                    "Sin hueco disponible. Amplía el rango de fechas, "
                    "añade más pistas o reduce la duración de los partidos."
                )
                # Contar el conflicto en su tanda para no bloquear la barrera
                # de tandas posteriores (un partido sin hueco no se juega).
                completed_per_wave[_wave_of(m)] += 1
                unscheduled.remove(m)
            continue

        # Orden de selección (lexicográfico):
        #   1. inicio más temprano  → compactación (no dejar pistas vacías)
        #   2. fin más temprano     → partidos cortos primero
        #   3. nº de tanda          → la tanda 1 (Masc+Fem) tiene prioridad; la
        #                             tanda 2 (Mixto) solo entra cuando la 1 no
        #                             puede llenar ese hueco → rellena la cola
        #   4. categoría menos colocada → mezcla categorías (evita 4-Masc o 4-Fem
        #                             seguidos cuando hay varias categorías listas)
        #   5. rotación de grupos   → evita bloques Grupo A, luego B, luego C
        #   6. nº de partido y UUID → determinismo
        candidates.sort(key=lambda c: (
            c[0],
            c[1],
            _wave_of(c[3]),
            placed_per_div[c[3].division],
            placed_per_group_name[_gid_to_name.get(c[3].group_id, "")],
            c[3].match_number,
            c[3].id,
        ))
        s_start, s_end, court, best_match = candidates[0]

        _session_day = s_start.date()
        if s_start.time() < _day_hours(s_start.date())[0]:
            _session_day = s_start.date() - timedelta(days=1)
        best_match.match_date = _session_day
        best_match.start_time = s_start.time()
        best_match.end_time   = s_end.time()
        best_match.court      = court
        best_match.status     = TMatchStatus.SCHEDULED

        court_tls[court.id].mark_occupied(s_end)
        # Registrar con jugadores potenciales (TBD → busca en rondas anteriores)
        # para que el _PlayerTimeline bloquee correctamente entre tandas.
        player_tl.record(
            _all_potential_player_keys(best_match, config.matches), s_end
        )
        if _distribute:
            _sched_day = best_match.match_date
            for _pk in _match_player_keys(best_match):
                _player_day_busy[_pk].add(_sched_day)

        _dk = (best_match.division, best_match.round)
        completed_rounds[_dk] += 1
        placed_per_div[best_match.division] += 1
        placed_per_group_name[_gid_to_name.get(best_match.group_id, "")] += 1
        if _dk not in div_round_latest or s_end > div_round_latest[_dk]:
            div_round_latest[_dk] = s_end
        # Barrera de tandas: contar el partido en su tanda y registrar su fin
        _wn = _wave_of(best_match)
        completed_per_wave[_wn] += 1
        if _wn not in wave_end_latest or s_end > wave_end_latest[_wn]:
            wave_end_latest[_wn] = s_end

        unscheduled.remove(best_match)

    # Conflictos residuales (si _safety se agotó o quedaron sin hueco)
    for m in unscheduled:
        m.status = TMatchStatus.CONFLICT
        m.conflict_reason = (
            "Sin hueco disponible. Amplía el rango de fechas, "
            "añade más pistas o reduce la duración de los partidos."
        )

    return config


def _ordered_wave_divisions(config: TournamentConfig, matches: list[TournamentMatch]) -> list[str | None]:
    """Divisiones de una tanda manteniendo el orden configurado por el usuario."""
    present = {m.division for m in matches}
    ordered: list[str | None] = [
        d for d in (getattr(config, "divisions", []) or [])
        if d in present
    ]
    for d in present:
        if d not in ordered:
            ordered.append(d)
    return ordered


def _interleave_matches_by_division(
    matches: list[TournamentMatch],
    divisions: list[str | None],
) -> list[TournamentMatch]:
    """Intercala categorias de la misma tanda para que avancen en paralelo."""
    if len(divisions) <= 1:
        return _interleave_matches_by_group(matches)

    by_division: dict[str | None, list[TournamentMatch]] = defaultdict(list)
    for match in matches:
        by_division[match.division].append(match)
    for idx, division in enumerate(divisions):
        if division in by_division:
            by_division[division] = _interleave_matches_by_group(by_division[division], offset=idx)

    ordered: list[TournamentMatch] = []
    while any(by_division.values()):
        for division in divisions:
            if by_division[division]:
                ordered.append(by_division[division].pop(0))
    return ordered


def _interleave_matches_by_group(matches: list[TournamentMatch], offset: int = 0) -> list[TournamentMatch]:
    """Rota grupos dentro de una categoria para evitar bloques A, luego B, luego C."""
    group_ids = [m.group_id for m in matches if m.group_id]
    if len(set(group_ids)) <= 1:
        return matches

    by_group: dict[str | None, list[TournamentMatch]] = defaultdict(list)
    group_order: list[str | None] = []
    fallback_order: list[str | None] = []
    for match in matches:
        key = match.group_id
        by_group[key].append(match)
        if key and key not in group_order:
            group_order.append(key)
        elif key is None and key not in fallback_order:
            fallback_order.append(key)

    ordered: list[TournamentMatch] = []
    if group_order:
        shift = offset % len(group_order)
        group_order = group_order[shift:] + group_order[:shift]
    rotation = group_order + fallback_order
    while any(by_group.values()):
        for group_id in rotation:
            if by_group[group_id]:
                ordered.append(by_group[group_id].pop(0))
    return ordered


def _duration_for_match(config: TournamentConfig, match: TournamentMatch) -> timedelta:
    """Duración real del partido según ronda."""
    minutes = config.match_duration_minutes
    if match.round == MatchRound.SEMIFINAL and getattr(config, "semifinal_duration_minutes", 0):
        minutes = config.semifinal_duration_minutes
    elif match.round in (MatchRound.FINAL, MatchRound.THIRD_PLACE) and getattr(config, "final_duration_minutes", 0):
        minutes = config.final_duration_minutes
    return timedelta(minutes=minutes)


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
    all_matches:   "list[TournamentMatch] | None" = None,
    blocked_days:  "set[date] | None" = None,
    day_hours_fn:  "callable | None" = None,
) -> Optional[tuple[datetime, datetime, TournamentCourt]]:
    """
    Devuelve (start, end, court) del hueco más temprano disponible
    entre todas las pistas y todos los días del torneo.

    La función COMPARA todas las pistas en cada día y elige la que
    permita el inicio más temprano — esto garantiza el uso en paralelo.

    Tiene en cuenta a TODOS los jugadores del partido: si alguno juega en otra
    categoría, no puede tener dos partidos a la vez.
    """
    # Momento más temprano en que todos los jugadores del partido están libres.
    # Usa jugadores potenciales (incl. TBD) para evitar solapamiento cross-wave.
    _am = all_matches or []
    players_avail = player_tl.available_from(
        _all_potential_player_keys(match, _am)
    )

    for d in all_days:
        # Modo distribución: si algún jugador ya tiene partido este día, saltar.
        if blocked_days and d in blocked_days:
            continue

        _d_start, _d_end = day_hours_fn(d) if day_hours_fn else (day_start, day_end)
        day_start_dt = _dt(d, _d_start)
        day_end_dt   = _day_end_dt(d, _d_end, _d_start)

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
