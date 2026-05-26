"""
Genera borradores de mensajes/emails para cada grupo o pareja.
No envía nada automáticamente — solo genera texto para revisión manual.
"""

from collections import defaultdict

from .models import Match, Group, Pair, MatchStatus

WEEKDAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

_DEFAULT_INTRO_GROUP = (
    "Hola a todos,\n\n"
    "Os dejamos los partidos programados para esta fase del ranking."
)
_DEFAULT_OUTRO = (
    "Por favor, revisad cualquier incidencia con {club_name}.\n\n"
    "¡Muchos ánimos y mucho pádel!\n\n"
    "– {club_name}"
)
_DEFAULT_INTRO_PAIR = "Hola {pair_name},\n\nAquí tenéis vuestros partidos del ranking:"
_DEFAULT_OUTRO_PAIR = (
    "Ante cualquier duda, contactad con {club_name}.\n\n"
    "¡Mucha suerte!\n– {club_name}"
)


def generate_group_message(
    group: Group,
    matches: list[Match],
    club_name: str = "El Club",
    intro_text: str | None = None,
    outro_text: str | None = None,
    include_court: bool = True,
) -> str:
    """
    Genera un mensaje con todos los partidos programados de un grupo.

    Args:
        intro_text: Párrafo inicial personalizado. Si es None usa el texto por defecto.
        outro_text: Párrafo final personalizado. Si es None usa el texto por defecto.
        include_court: Si False, omite el nombre de pista (útil para mensajes a jugadores).
    """
    scheduled = [m for m in matches if m.group_id == group.id and m.status == MatchStatus.SCHEDULED]
    scheduled.sort(key=lambda m: (m.suggested_date, m.suggested_start_time))  # type: ignore

    intro = (intro_text or _DEFAULT_INTRO_GROUP).format(club_name=club_name, group_name=group.name)
    outro = (outro_text or _DEFAULT_OUTRO).format(club_name=club_name, group_name=group.name)

    lines = [intro, "", f"🎾 {group.name}", ""]

    if not scheduled:
        lines.append("⚠️ No hay partidos programados aún para este grupo.")
    else:
        for m in scheduled:
            wd = m.suggested_date.weekday() if m.suggested_date else None
            fecha_str = (
                f"{WEEKDAY_ES[wd].capitalize()} {m.suggested_date.strftime('%d/%m/%Y')}"
                if m.suggested_date and wd is not None
                else "Por confirmar"
            )
            hora_inicio = m.suggested_start_time.strftime("%H:%M") if m.suggested_start_time else "--"
            hora_fin    = m.suggested_end_time.strftime("%H:%M") if m.suggested_end_time else "--"
            pista       = m.court.name if m.court else "Por confirmar"

            block = [
                f"🔹 {m.pair_1.display_name}  vs  {m.pair_2.display_name}",
                f"   📅 {fecha_str}",
                f"   🕐 {hora_inicio} – {hora_fin}",
            ]
            if include_court:
                block.append(f"   🏟️ {pista}")
            block.append("")
            lines.extend(block)

    lines.append(outro)
    return "\n".join(lines)


def generate_pair_message(
    pair: Pair,
    matches: list[Match],
    club_name: str = "El Club",
    intro_text: str | None = None,
    outro_text: str | None = None,
    include_court: bool = True,
) -> str:
    """
    Genera un mensaje personalizado para una pareja con sus partidos.

    Args:
        intro_text: Párrafo inicial personalizado. Si es None usa el texto por defecto.
        outro_text: Párrafo final personalizado. Si es None usa el texto por defecto.
        include_court: Si False, omite el nombre de pista.
    """
    pair_matches = [
        m for m in matches
        if (m.pair_1.id == pair.id or m.pair_2.id == pair.id)
        and m.status == MatchStatus.SCHEDULED
    ]
    pair_matches.sort(key=lambda m: (m.suggested_date, m.suggested_start_time))  # type: ignore

    intro = (intro_text or _DEFAULT_INTRO_PAIR).format(
        club_name=club_name, pair_name=pair.display_name
    )
    outro = (outro_text or _DEFAULT_OUTRO_PAIR).format(
        club_name=club_name, pair_name=pair.display_name
    )

    lines = [intro, ""]

    if not pair_matches:
        lines.append("⚠️ No tenéis partidos programados todavía.")
    else:
        for m in pair_matches:
            rival   = m.pair_2 if m.pair_1.id == pair.id else m.pair_1
            wd      = m.suggested_date.weekday() if m.suggested_date else None
            fecha_str = (
                f"{WEEKDAY_ES[wd].capitalize()} {m.suggested_date.strftime('%d/%m/%Y')}"
                if m.suggested_date and wd is not None
                else "Por confirmar"
            )
            hora_inicio = m.suggested_start_time.strftime("%H:%M") if m.suggested_start_time else "--"
            hora_fin    = m.suggested_end_time.strftime("%H:%M") if m.suggested_end_time else "--"
            pista       = m.court.name if m.court else "Por confirmar"

            block = [
                f"🔹 Rival: {rival.display_name}",
                f"   📅 {fecha_str}",
                f"   🕐 {hora_inicio} – {hora_fin}",
            ]
            if include_court:
                block.append(f"   🏟️ {pista}")
            block.append("")
            lines.extend(block)

    lines.append(outro)
    return "\n".join(lines)


def generate_all_group_messages(
    groups: list[Group],
    matches: list[Match],
    club_name: str = "El Club",
    intro_text: str | None = None,
    outro_text: str | None = None,
    include_court: bool = True,
) -> dict[str, str]:
    """Devuelve {group_id: mensaje_texto}."""
    return {
        g.id: generate_group_message(
            g, matches, club_name,
            intro_text=intro_text, outro_text=outro_text, include_court=include_court,
        )
        for g in groups
    }


def generate_all_pair_messages(
    groups: list[Group],
    matches: list[Match],
    club_name: str = "El Club",
    intro_text: str | None = None,
    outro_text: str | None = None,
    include_court: bool = True,
) -> dict[str, str]:
    """Devuelve {pair_id: mensaje_texto}."""
    result = {}
    for g in groups:
        for pair in g.pairs:
            result[pair.id] = generate_pair_message(
                pair, matches, club_name,
                intro_text=intro_text, outro_text=outro_text, include_court=include_court,
            )
    return result
