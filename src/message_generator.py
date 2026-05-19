"""
Genera borradores de mensajes/emails para cada grupo o pareja.
No envía nada automáticamente — solo genera texto para revisión manual.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Match, Group, Pair, MatchStatus


def generate_group_message(group: Group, matches: list[Match], club_name: str = "El Club") -> str:
    """
    Genera un mensaje con todos los partidos programados de un grupo.
    """
    scheduled = [m for m in matches if m.group_id == group.id and m.status == MatchStatus.SCHEDULED]
    scheduled.sort(key=lambda m: (m.suggested_date, m.suggested_start_time))  # type: ignore

    lines = [
        f"Hola a todos,",
        f"",
        f"Os dejamos los partidos programados para esta fase del ranking.",
        f"",
        f"🎾 {group.name}",
        f"",
    ]

    if not scheduled:
        lines.append("⚠️ No hay partidos programados aún para este grupo.")
    else:
        for m in scheduled:
            fecha = m.suggested_date.strftime("%A %d/%m/%Y") if m.suggested_date else "Por confirmar"
            hora_inicio = m.suggested_start_time.strftime("%H:%M") if m.suggested_start_time else "--"
            hora_fin = m.suggested_end_time.strftime("%H:%M") if m.suggested_end_time else "--"
            pista = m.court.name if m.court else "Por confirmar"
            lines += [
                f"🔹 {m.pair_1.display_name}  vs  {m.pair_2.display_name}",
                f"   📅 {fecha.capitalize()}",
                f"   🕐 {hora_inicio} – {hora_fin}",
                f"   🏟️ {pista}",
                f"",
            ]

    lines += [
        f"Por favor, revisad cualquier incidencia con {club_name}.",
        f"",
        f"¡Muchos ánimos y mucho pádel!",
        f"",
        f"– {club_name}",
    ]

    return "\n".join(lines)


def generate_pair_message(pair: Pair, matches: list[Match], club_name: str = "El Club") -> str:
    """
    Genera un mensaje personalizado para una pareja con sus partidos.
    """
    pair_matches = [
        m for m in matches
        if (m.pair_1.id == pair.id or m.pair_2.id == pair.id)
        and m.status == MatchStatus.SCHEDULED
    ]
    pair_matches.sort(key=lambda m: (m.suggested_date, m.suggested_start_time))  # type: ignore

    lines = [
        f"Hola {pair.display_name},",
        f"",
        f"Aquí tenéis vuestros partidos del ranking:",
        f"",
    ]

    if not pair_matches:
        lines.append("⚠️ No tenéis partidos programados todavía.")
    else:
        for m in pair_matches:
            rival = m.pair_2 if m.pair_1.id == pair.id else m.pair_1
            fecha = m.suggested_date.strftime("%A %d/%m/%Y") if m.suggested_date else "Por confirmar"
            hora_inicio = m.suggested_start_time.strftime("%H:%M") if m.suggested_start_time else "--"
            hora_fin = m.suggested_end_time.strftime("%H:%M") if m.suggested_end_time else "--"
            pista = m.court.name if m.court else "Por confirmar"
            lines += [
                f"🔹 Rival: {rival.display_name}",
                f"   📅 {fecha.capitalize()}",
                f"   🕐 {hora_inicio} – {hora_fin}",
                f"   🏟️ {pista}",
                f"",
            ]

    lines += [
        f"Ante cualquier duda, contactad con {club_name}.",
        f"",
        f"¡Mucha suerte!",
        f"– {club_name}",
    ]

    return "\n".join(lines)


def generate_all_group_messages(
    groups: list[Group],
    matches: list[Match],
    club_name: str = "El Club",
) -> dict[str, str]:
    """Devuelve {group_id: mensaje_texto}."""
    return {
        g.id: generate_group_message(g, matches, club_name)
        for g in groups
    }


def generate_all_pair_messages(
    groups: list[Group],
    matches: list[Match],
    club_name: str = "El Club",
) -> dict[str, str]:
    """Devuelve {pair_id: mensaje_texto}."""
    result = {}
    for g in groups:
        for pair in g.pairs:
            result[pair.id] = generate_pair_message(pair, matches, club_name)
    return result
