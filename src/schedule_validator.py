"""
Validación post-asignación del calendario generado.

Comprueba:
  1. Un jugador con 2 partidos el mismo día (cross-ranking incluido)
  2. Disponibilidad de la pareja: día de la semana
  3. Disponibilidad de la pareja: franja horaria
  4. Separación mínima entre partidos de la misma pareja (min_days_between_matches)
  5. Máximo de partidos por semana de la misma pareja (max_matches_per_week)
  6. Pista fija (PF): el partido debería estar en el día/hora preferido
  7. Doble reserva en la misma pista al mismo tiempo

Cada infracción se representa como un dict con:
  - type        : código de tipo
  - severity    : "error" | "warning" | "info"
  - description : texto legible
  - matches     : lista de Match implicados
  - pair_names  : lista de nombres de pareja implicados
"""

from collections import defaultdict
from datetime import date, time, timedelta

from .models import Match, MatchStatus, RankingPhase, ScheduleResult


# ----------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------

SEVERITY_EMOJI = {"error": "🔴", "warning": "🟡", "info": "🔵"}

WEEKDAY_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _pair_pf_slots(pair) -> list[tuple[int, time]]:
    """
    Devuelve todas las franjas PF de una pareja como (weekday, time),
    soportando formato nuevo (preferred_slots) y legado (preferred_weekday/time).
    """
    slots: list[tuple[int, time]] = []
    seen: set[tuple[int, time]] = set()

    raw_slots = getattr(pair, "preferred_slots", None) or []
    for item in raw_slots:
        wd = None
        tt = None
        if isinstance(item, dict):
            wd = item.get("weekday")
            tt = item.get("time")
        else:
            wd = getattr(item, "weekday", None)
            tt = getattr(item, "time", None)
        if isinstance(wd, int) and isinstance(tt, time):
            key = (wd, tt)
            if key not in seen:
                seen.add(key)
                slots.append(key)

    pw = getattr(pair, "preferred_weekday", None)
    pt = getattr(pair, "preferred_time", None)
    if isinstance(pw, int) and isinstance(pt, time):
        key = (pw, pt)
        if key not in seen:
            seen.add(key)
            slots.append(key)

    return slots


def _slot_matches_pair_pf(pair, wd: int, st: time) -> bool:
    return any((wd == pf_wd and st == pf_t) for pf_wd, pf_t in _pair_pf_slots(pair))


# ----------------------------------------------------------------
# Función principal
# ----------------------------------------------------------------

def validate_schedule(
    result: ScheduleResult,
    phase: RankingPhase,
) -> list[dict]:
    """
    Ejecuta todas las validaciones sobre los partidos programados.
    Devuelve una lista de violaciones ordenadas por severidad.
    """
    violations: list[dict] = []

    scheduled = [
        m for m in result.scheduled
        if m.suggested_date and m.suggested_start_time
    ]

    if not scheduled:
        return violations

    # ----------------------------------------------------------------
    # 0. Partidos en sábado/domingo (nunca deben existir)
    # ----------------------------------------------------------------
    for m in scheduled:
        wd = m.suggested_date.weekday()
        if wd >= 5:
            violations.append({
                "type": "weekend_match",
                "severity": "error",
                "description": (
                    f"{m.label}: partido el {WEEKDAY_ES[wd]} "
                    f"{m.suggested_date.strftime('%d/%m/%Y')} — el ranking solo es L-V"
                ),
                "matches": [m],
                "pair_names": [m.pair_1.display_name, m.pair_2.display_name],
            })

    # Índices auxiliares
    pair_matches: dict[str, list[Match]] = defaultdict(list)
    player_day: dict[tuple, list[Match]] = defaultdict(list)   # (player_id, date) → matches
    court_slot: dict[tuple, list[Match]] = defaultdict(list)   # (court_id, date, time) → matches

    for m in scheduled:
        pair_matches[m.pair_1.id].append(m)
        pair_matches[m.pair_2.id].append(m)

        for pid in (
            m.pair_1.player_1.id, m.pair_1.player_2.id,
            m.pair_2.player_1.id, m.pair_2.player_2.id,
        ):
            player_day[(pid, m.suggested_date)].append(m)

        if m.court:
            court_slot[(m.court.id, m.suggested_date, m.suggested_start_time)].append(m)

    # ----------------------------------------------------------------
    # 1. Jugador con 2 partidos el mismo día
    # ----------------------------------------------------------------
    player_id_to_name: dict[str, str] = {}
    for m in scheduled:
        player_id_to_name[m.pair_1.player_1.id] = m.pair_1.player_1.full_name
        player_id_to_name[m.pair_1.player_2.id] = m.pair_1.player_2.full_name
        player_id_to_name[m.pair_2.player_1.id] = m.pair_2.player_1.full_name
        player_id_to_name[m.pair_2.player_2.id] = m.pair_2.player_2.full_name

    reported_player_day: set[tuple] = set()
    for (pid, d), matches in player_day.items():
        if len(matches) > 1:
            key = (pid, d)
            if key in reported_player_day:
                continue
            reported_player_day.add(key)
            pname = player_id_to_name.get(pid, pid)
            violations.append({
                "type": "player_double_day",
                "severity": "error",
                "description": (
                    f"{pname} tiene {len(matches)} partidos el "
                    f"{d.strftime('%d/%m/%Y')} ({WEEKDAY_ES[d.weekday()]})"
                ),
                "matches": matches,
                "pair_names": [pname],
            })

    # ----------------------------------------------------------------
    # 2. Doble reserva en la misma pista y hora
    # ----------------------------------------------------------------
    for (cid, d, slot_time), matches in court_slot.items():
        if len(matches) > 1:
            court_name = matches[0].court.name if matches[0].court else cid
            violations.append({
                "type": "court_double_booking",
                "severity": "error",
                "description": (
                    f"{court_name} tiene {len(matches)} partidos a las "
                    f"{slot_time.strftime('%H:%M')} del {d.strftime('%d/%m/%Y')}"
                ),
                "matches": matches,
                "pair_names": [m.label for m in matches],
            })

    # ----------------------------------------------------------------
    # 3. Disponibilidad: día de la semana
    # Excepción PF: si la pareja tiene pista fija en ese día (preferred_weekday),
    # la colocación es intencionada aunque ese día no esté en available_weekdays
    # (el scheduler la permite mediante el override PF). No se reporta.
    # ----------------------------------------------------------------
    for m in scheduled:
        wd = m.suggested_date.weekday()
        st = m.suggested_start_time
        for pair in (m.pair_1, m.pair_2):
            # Si el partido cae en la pista fija de la pareja, no es una infracción
            if _slot_matches_pair_pf(pair, wd, st):
                continue
            if pair.available_weekdays and wd not in pair.available_weekdays:
                avail_str = ", ".join(WEEKDAY_ES[d] for d in pair.available_weekdays)
                violations.append({
                    "type": "availability_weekday",
                    "severity": "warning",
                    "description": (
                        f"{pair.display_name}: partido el {WEEKDAY_ES[wd]} "
                        f"{m.suggested_date.strftime('%d/%m/%Y')} pero disponible "
                        f"solo {avail_str}"
                    ),
                    "matches": [m],
                    "pair_names": [pair.display_name],
                })

    # ----------------------------------------------------------------
    # 4. Disponibilidad: franja horaria
    # available_until = hora máxima de INICIO (inclusiva) → st > until es violación
    # ----------------------------------------------------------------
    for m in scheduled:
        st = m.suggested_start_time
        wd = m.suggested_date.weekday()
        for pair in (m.pair_1, m.pair_2):
            # Determinar ventana efectiva para este día
            pdw = getattr(pair, "per_day_windows", {})
            if pdw and wd in pdw:
                win   = pdw[wd]
                wfrom = win.get("from")
                wuntil = win.get("until")
            else:
                wfrom  = pair.available_from
                wuntil = pair.available_until

            # PF override: si coincide con preferred_weekday+preferred_time, no reportar
            if _slot_matches_pair_pf(pair, wd, st):
                continue

            if wfrom and st < wfrom:
                violations.append({
                    "type": "availability_time_early",
                    "severity": "warning",
                    "description": (
                        f"{pair.display_name}: partido a las {st.strftime('%H:%M')} "
                        f"pero disponible desde {wfrom.strftime('%H:%M')}"
                    ),
                    "matches": [m],
                    "pair_names": [pair.display_name],
                })
            if wuntil and st > wuntil:
                violations.append({
                    "type": "availability_time_late",
                    "severity": "warning",
                    "description": (
                        f"{pair.display_name}: partido a las {st.strftime('%H:%M')} "
                        f"pero disponible solo hasta {wuntil.strftime('%H:%M')} (inclusivo)"
                    ),
                    "matches": [m],
                    "pair_names": [pair.display_name],
                })

    # ----------------------------------------------------------------
    # 5. Separación mínima entre partidos de la misma pareja
    # ----------------------------------------------------------------
    min_days = phase.min_days_between_matches
    if min_days > 0:
        for pair_id, matches in pair_matches.items():
            sorted_m = sorted(matches, key=lambda m: m.suggested_date)
            for i in range(len(sorted_m) - 1):
                diff = (sorted_m[i + 1].suggested_date - sorted_m[i].suggested_date).days
                if diff < min_days:
                    pair_name = (sorted_m[i].pair_1.display_name
                                 if sorted_m[i].pair_1.id == pair_id
                                 else sorted_m[i].pair_2.display_name)
                    violations.append({
                        "type": "min_days_violation",
                        "severity": "warning",
                        "description": (
                            f"{pair_name}: partidos con solo {diff} día(s) de separación "
                            f"({sorted_m[i].suggested_date.strftime('%d/%m')} y "
                            f"{sorted_m[i+1].suggested_date.strftime('%d/%m/%Y')}, "
                            f"mínimo: {min_days} días)"
                        ),
                        "matches": [sorted_m[i], sorted_m[i + 1]],
                        "pair_names": [pair_name],
                    })

    # ----------------------------------------------------------------
    # 6. Máximo de partidos por semana
    # ----------------------------------------------------------------
    max_week = phase.max_matches_per_week

    def _week(d: date) -> int:
        return d.isocalendar()[1]

    for pair_id, matches in pair_matches.items():
        by_week: dict[int, list[Match]] = defaultdict(list)
        for m in matches:
            by_week[_week(m.suggested_date)].append(m)
        for wk, wk_matches in by_week.items():
            if len(wk_matches) > max_week:
                first_m = wk_matches[0]
                pair_name = (first_m.pair_1.display_name
                             if first_m.pair_1.id == pair_id
                             else first_m.pair_2.display_name)
                violations.append({
                    "type": "max_week_violation",
                    "severity": "warning",
                    "description": (
                        f"{pair_name}: {len(wk_matches)} partidos en la semana {wk} "
                        f"(máximo: {max_week})"
                    ),
                    "matches": wk_matches,
                    "pair_names": [pair_name],
                })

    # ----------------------------------------------------------------
    # 7. Pista fija (PF): partido no coincide con día/hora preferido
    #
    # Caso importante: si AMBAS parejas tienen PF en franjas distintas, el
    # partido solo puede estar en UNA de las dos. Si cae en la PF de alguna
    # de ellas, es el mejor resultado posible y NO se reporta como infracción.
    # Solo se reporta si el partido no coincide con la PF de NINGUNA pareja.
    # ----------------------------------------------------------------
    def _match_on_pf(pair, wd, st) -> bool:
        return _slot_matches_pair_pf(pair, wd, st)

    for m in scheduled:
        wd = m.suggested_date.weekday()
        st = m.suggested_start_time
        pf_pairs = [p for p in (m.pair_1, m.pair_2) if _pair_pf_slots(p)]
        if not pf_pairs:
            continue

        # Si el partido cae en la PF de alguna pareja → asignación óptima, no reportar
        if any(_match_on_pf(p, wd, st) for p in pf_pairs):
            continue

        # No coincide con ninguna PF → reportar para cada pareja con PF
        for pair in pf_pairs:
            pref = [f"{WEEKDAY_ES[pw]} {pt.strftime('%H:%M')}" for pw, pt in _pair_pf_slots(pair)]
            assigned = f"{WEEKDAY_ES[wd]} {st.strftime('%H:%M')}"
            violations.append({
                "type": "preferred_slot_mismatch",
                "severity": "info",
                "description": (
                    f"{pair.display_name} (PF {' / '.join(pref)}): "
                    f"partido asignado el {assigned}"
                ),
                "matches": [m],
                "pair_names": [pair.display_name],
            })

    # Ordenar: errors primero, luego warnings, luego info
    order = {"error": 0, "warning": 1, "info": 2}
    violations.sort(key=lambda v: order.get(v["severity"], 9))
    return violations


# ----------------------------------------------------------------
# Resumen rápido (para mostrar tras la asignación)
# ----------------------------------------------------------------

def validation_summary(violations: list[dict]) -> dict:
    errors   = sum(1 for v in violations if v["severity"] == "error")
    warnings = sum(1 for v in violations if v["severity"] == "warning")
    infos    = sum(1 for v in violations if v["severity"] == "info")
    return {"errors": errors, "warnings": warnings, "infos": infos, "total": len(violations)}
