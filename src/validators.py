"""
Validaciones de datos importados (CSV / Syltek).
Devuelve listas de errores en lugar de lanzar excepciones para que la UI
pueda mostrarlos al usuario sin romper el flujo.
"""

import unicodedata
from typing import Any
import pandas as pd

from .models import Group, Pair, Player


ValidationErrors = list[str]

# Diccionario con severidad para validate_groups (más rico que solo strings)
# {"severity": "error"|"warning"|"info", "message": str}
ValidationIssue = dict
ValidationIssues = list[ValidationIssue]

EXPECTED_GROUP_SIZE = 6   # Tamaño estándar de grupo en el ranking


def _normalize_name(name: str) -> str:
    """Normaliza un nombre para comparación (minúsculas, sin acentos)."""
    raw = name.strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def validate_groups_df(df: pd.DataFrame) -> ValidationErrors:
    """Valida un DataFrame de grupos con columnas: group_id, group_name, pair_name, player1_name, player2_name."""
    errors: ValidationErrors = []
    required = {"group_id", "group_name", "pair_name", "player1_name", "player2_name"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Faltan columnas obligatorias: {', '.join(missing)}")
        return errors  # no tiene sentido continuar

    for i, row in df.iterrows():
        row_id = f"fila {i + 2}"
        if pd.isna(row.get("group_id")) or str(row["group_id"]).strip() == "":
            errors.append(f"{row_id}: group_id vacío.")
        if pd.isna(row.get("pair_name")) or str(row["pair_name"]).strip() == "":
            errors.append(f"{row_id}: pair_name vacío.")
        if pd.isna(row.get("player1_name")) or str(row["player1_name"]).strip() == "":
            errors.append(f"{row_id}: player1_name vacío.")
        if pd.isna(row.get("player2_name")) or str(row["player2_name"]).strip() == "":
            errors.append(f"{row_id}: player2_name vacío.")

    return errors


def validate_bookings_df(df: pd.DataFrame) -> ValidationErrors:
    """Valida DataFrame de reservas con columnas: court_name, start_datetime, end_datetime."""
    errors: ValidationErrors = []
    required = {"court_name", "start_datetime", "end_datetime"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Faltan columnas obligatorias: {', '.join(missing)}")
        return errors

    for i, row in df.iterrows():
        row_id = f"fila {i + 2}"
        try:
            start = pd.to_datetime(row["start_datetime"])
            end = pd.to_datetime(row["end_datetime"])
            if start >= end:
                errors.append(f"{row_id}: start_datetime >= end_datetime.")
        except Exception:
            errors.append(f"{row_id}: fechas no parseable.")

    return errors


def validate_availability_df(df: pd.DataFrame) -> ValidationErrors:
    """Valida DataFrame de disponibilidad con columnas: court_name, date, start_time, end_time."""
    errors: ValidationErrors = []
    required = {"court_name", "date", "start_time", "end_time"}
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Faltan columnas obligatorias: {', '.join(missing)}")
    return errors


def validate_phase_dates(start: Any, end: Any) -> ValidationErrors:
    errors: ValidationErrors = []
    if start is None or end is None:
        errors.append("Las fechas de inicio y fin son obligatorias.")
        return errors
    if start >= end:
        errors.append("La fecha de inicio debe ser anterior a la fecha de fin.")
    return errors


def validate_required_text(value: Any, field_label: str) -> ValidationErrors:
    """
    Valida que un campo de texto obligatorio no esté vacío.
    """
    if value is None or str(value).strip() == "":
        return [f"{field_label} es obligatorio."]
    return []


def validate_groups(groups: list[Group]) -> ValidationIssues:
    """
    Valida la estructura de los grupos cargados.

    Comprueba:
    1. Tamaño del grupo (error si < 2, aviso si != 6).
    2. Jugadores duplicados dentro del mismo grupo (un jugador en dos parejas).
    3. Parejas con el mismo ID en distintos grupos.
    4. Parejas sin ningún dato de contacto (email ni teléfono) en ninguno de sus jugadores.

    Devuelve una lista de dicts con claves:
      - severity : "error" | "warning" | "info"
      - message  : texto legible
    """
    issues: ValidationIssues = []
    seen_pair_ids: set[str] = set()

    for g in groups:
        n = len(g.pairs)

        # ── 1. Tamaño del grupo
        if n < 2:
            issues.append({
                "severity": "error",
                "message": f"Grupo '{g.name}': necesita al menos 2 parejas para generar partidos.",
            })
        elif n != EXPECTED_GROUP_SIZE:
            issues.append({
                "severity": "warning",
                "message": (
                    f"Grupo '{g.name}': tiene {n} pareja{'s' if n != 1 else ''} "
                    f"(se esperan {EXPECTED_GROUP_SIZE} para el round-robin completo)."
                ),
            })

        # ── 2. Jugadores duplicados dentro del grupo
        player_seen: dict[str, str] = {}   # normalized_name → pair display name
        for pair in g.pairs:
            for player in (pair.player_1, pair.player_2):
                key = _normalize_name(player.full_name)
                if not key:
                    continue
                if key in player_seen:
                    issues.append({
                        "severity": "error",
                        "message": (
                            f"Grupo '{g.name}': el jugador '{player.full_name}' aparece "
                            f"en más de una pareja ('{player_seen[key]}' y '{pair.display_name}')."
                        ),
                    })
                else:
                    player_seen[key] = pair.display_name

        # ── 3. IDs de pareja duplicados entre grupos
        for pair in g.pairs:
            if pair.id in seen_pair_ids:
                issues.append({
                    "severity": "error",
                    "message": f"Pareja duplicada '{pair.display_name}' aparece en varios grupos.",
                })
            seen_pair_ids.add(pair.id)

        # ── 4. Parejas sin contacto
        for pair in g.pairs:
            p1_has_contact = bool(pair.player_1.email or pair.player_1.phone)
            p2_has_contact = bool(pair.player_2.email or pair.player_2.phone)
            missing_names = []
            if not p1_has_contact:
                missing_names.append(pair.player_1.full_name)
            if not p2_has_contact:
                missing_names.append(pair.player_2.full_name)
            if missing_names:
                issues.append({
                    "severity": "info",
                    "message": (
                        f"Grupo '{g.name}', pareja '{pair.display_name}': "
                        f"sin email ni teléfono para {', '.join(missing_names)}."
                    ),
                })

    return issues


def issues_summary(issues: ValidationIssues) -> dict:
    """Cuenta errores/warnings/infos para mostrar un resumen rápido."""
    errors   = sum(1 for v in issues if v["severity"] == "error")
    warnings = sum(1 for v in issues if v["severity"] == "warning")
    infos    = sum(1 for v in issues if v["severity"] == "info")
    return {"errors": errors, "warnings": warnings, "infos": infos, "total": len(issues)}
