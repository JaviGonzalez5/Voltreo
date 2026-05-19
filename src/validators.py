"""
Validaciones de datos importados (CSV / Syltek).
Devuelve listas de errores en lugar de lanzar excepciones para que la UI
pueda mostrarlos al usuario sin romper el flujo.
"""

from typing import Any
import pandas as pd

from .models import Group, Pair, Player


ValidationErrors = list[str]


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


def validate_groups(groups: list[Group]) -> ValidationErrors:
    errors: ValidationErrors = []
    seen_pair_ids: set[str] = set()
    for g in groups:
        if len(g.pairs) < 2:
            errors.append(f"Grupo '{g.name}': necesita al menos 2 parejas para generar partidos.")
        for p in g.pairs:
            if p.id in seen_pair_ids:
                errors.append(f"Pareja duplicada '{p.display_name}' en varios grupos.")
            seen_pair_ids.add(p.id)
    return errors
