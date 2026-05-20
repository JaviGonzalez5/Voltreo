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
from datetime import date, time, datetime, timedelta

from .models import Match, MatchStatus, RankingPhase, ScheduleResult


# ----------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------

SEVERITY_EMOJI = {"error": "🔴", "warning": "🟡", "info": "🔵"}

WEEKDAY_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


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

    # Índices auxiliares
    pair_matches: dict[str, list[Match]] = defaultdict(list)
    player_day: dict[tuple, list[Match]] = defaultdict(list)   # (player_id, date) → matches
    court_slot: dict[tuple, list[Match]] = defaultdict(list)   # (court_id, date, time) → matches
    court_matches: dict[str, list[Match]] = defaultdict(list)  # para detectar solapes con inicios distintos

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
            court_matches[m.court.id].append(m)

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
    for (cid, d, t), matches in court_slot.items():
        if len(matches) > 1:
            court_name = matches[0].court.name if matches[0].court else cid
            violations.append({
                "type": "court_double_booking",
                "severity": "error",
                "description": (
                    f"{court_name} tiene {len(matches)} partidos a las "
                    f"{t.strftime('%H:%M')} del {d.strftime('%d/%m/%Y')}"
                ),
                "matches": matches,
                "pair_names": [m.label for m in matches],
            })


    # 2b. Solapes en la misma pista con distintas horas de inicio
    def _dt(d: date, t: time) -> datetime:
        return datetime.combine(d, t)

    for cid, ms in court_matches.items():
        sorted_ms = sorted(ms, key=lambda m: (m.suggested_date, m.suggested_start_time))
        for i in range(len(sorted_ms)):
            a = sorted_ms[i]
            for b in sorted_ms[i + 1:]:
                if a.suggested_date != b.suggested_date:
                    continue
                if b.suggested_start_time >= a.suggested_end_time:
                    break
                if _dt(a.suggested_date, a.suggested_start_time) < _dt(b.suggested_date, b.suggested_end_time) and _dt(b.suggested_date, b.suggested_start_time) < _dt(a.suggested_date, a.suggested_end_time):
                    court_name = a.court.name if a.court else cid
                    violations.append({
                        "type": "court_overlap",
                        "severity": "error",
                        "description": (
                            f"{court_name} tiene partidos solapados el "
                            f"{a.suggested_date.strftime('%d/%m/%Y')}: "
                            f"{a.suggested_start_time.strftime('%H:%M')}-{a.suggested_end_time.strftime('%H:%M')} "
                            f"y {b.suggested_start_time.strftime('%H:%M')}-{b.suggested_end_time.strftime('%H:%M')}"
                        ),
                        "matches": [a, b],
                        "pair_names": [a.label, b.label],
                    })

    # ----------------------------------------------------------------
    # 3. Disponibilidad: día de la semana
    # ----------------------------------------------------------------
    for m in scheduled:
        wd = m.suggested_date.weekday()
        for pair in (m.pair_1, m.pair_2):
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
    # ----------------------------------------------------------------
    for m in scheduled:
        st = m.suggested_start_time
        for pair in (m.pair_1, m.pair_2):
            if pair.available_from and st < pair.available_from:
                violations.append({
                    "type": "availability_time_early",
                    "severity": "warning",
                    "description": (
                        f"{pair.display_name}: partido a las {st.strftime('%H:%M')} "
                        f"pero disponible desde {pair.available_from.strftime('%H:%M')}"
                    ),
                    "matches": [m],
                    "pair_names": [pair.display_name],
                })
            if pair.available_until and st > pair.available_until:
                violations.append({
                    "type": "availability_time_late",
                    "severity": "warning",
                    "description": (
                        f"{pair.display_name}: partido empieza a las {st.strftime('%H:%M')} "
                        f"pero la última hora de inicio permitida es {pair.available_until.strftime('%H:%M')}"
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
                    pair_name = sorted_m[i].pair_1.display_name if sorted_m[i].pair_1.id == pair_id else sorted_m[i].pair_2.display_name
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
    # ----------------------------------------------------------------
    for m in scheduled:
        for pair in (m.pair_1, m.pair_2):
            pw = pair.preferred_weekday
            pt = pair.preferred_time
            if pw is None and pt is None:
                continue
            wd = m.suggested_date.weekday()
            st = m.suggested_start_time
            mismatch_day  = pw is not None and wd != pw
            mismatch_time = pt is not None and st != pt
            if mismatch_day or mismatch_time:
                pref = []
                if pw is not None:
                    pref.append(f"{WEEKDAY_ES[pw]}")
                if pt is not None:
                    pref.append(f"{pt.strftime('%H:%M')}")
                assigned = f"{WEEKDAY_ES[wd]} {st.strftime('%H:%M')}"
                violations.append({
                    "type": "preferred_slot_mismatch",
                    "severity": "info",
                    "description": (
                        f"{pair.display_name} (PF {' '.join(pref)}): "
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
