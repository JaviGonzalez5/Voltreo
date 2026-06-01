"""
Conversión entre modelos Pydantic y registros de base de datos.

Reglas:
  · El scheduler y los modelos NO saben nada de Supabase.
  · Esta capa hace la traducción en los dos sentidos.
  · Se usa Pydantic .model_dump(mode='json') para serializar
    (convierte date/time a strings ISO automáticamente).
  · Se usa model.model_validate(data) para deserializar.
"""

from typing import Optional

from .models import (
    RankingPhase, ScheduleResult, Group, Booking, BalanceWeights,
    Court, Match, Pair, Player,
)


# ---------------------------------------------------------------------------
# RankingPhase → DB payload
# ---------------------------------------------------------------------------

def phase_to_db(phase: RankingPhase, club_id: str, phase_id: Optional[str] = None) -> dict:
    """
    Serializa un RankingPhase al formato esperado por SupabaseDB.upsert_phase().

    Devuelve un dict con las claves:
      club_id, name, start_date, end_date,
      phase_config, groups_data, bookings_data
    (schedule_result se pasa por separado).
    """
    # Configuración de la fase sin groups ni bookings
    config_dict = phase.model_dump(mode="json", exclude={"groups", "bookings", "id"})

    groups_list  = [g.model_dump(mode="json") for g in phase.groups]
    bookings_list = [b.model_dump(mode="json") for b in phase.bookings]

    return {
        "phase_id":      phase_id,
        "club_id":       club_id,
        "name":          phase.name,
        "start_date":    phase.start_date.isoformat(),
        "end_date":      phase.end_date.isoformat(),
        "phase_config":  config_dict,
        "groups_data":   groups_list,
        "bookings_data": bookings_list,
    }


def schedule_result_to_db(result: ScheduleResult) -> Optional[dict]:
    """Serializa ScheduleResult a dict JSON para guardar en DB."""
    if result is None:
        return None
    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# DB → RankingPhase
# ---------------------------------------------------------------------------

def phase_from_db(row: dict) -> "tuple[RankingPhase, Optional[ScheduleResult]]":
    """
    Deserializa un registro de ranking_phases en (RankingPhase, ScheduleResult | None).

    RankingPhase tendrá ya sus groups y bookings cargados.
    """
    config  = row.get("phase_config") or {}
    g_data  = row.get("groups_data")  or []
    b_data  = row.get("bookings_data") or []
    sr_data = row.get("schedule_result")

    # Reconstruir grupos
    groups   = [Group.model_validate(g) for g in g_data]
    bookings = [Booking.model_validate(b) for b in b_data]

    # Reconstruir fase completa
    phase_data = dict(config)
    phase_data["id"]       = row["id"]
    phase_data["name"]     = row["name"]
    phase_data["start_date"] = row["start_date"]
    phase_data["end_date"]   = row["end_date"]
    phase_data["groups"]   = groups
    phase_data["bookings"] = bookings

    phase = RankingPhase.model_validate(phase_data)

    # Reconstruir resultado del calendario
    result: Optional[ScheduleResult] = None
    if sr_data:
        try:
            result = ScheduleResult.model_validate(sr_data)
        except Exception:
            result = None

    return phase, result


# ---------------------------------------------------------------------------
# TournamentConfig → DB / DB → TournamentConfig
# ---------------------------------------------------------------------------

def tournament_to_db(config, club_id: str, tournament_id: Optional[str] = None) -> dict:
    """Serializa TournamentConfig al formato de upsert_tournament()."""
    from .tournament_models import TournamentConfig
    data = config.model_dump(mode="json")
    return {
        "tournament_id":   tournament_id,
        "club_id":         club_id,
        "name":            config.name,
        "start_date":      config.start_date.isoformat(),
        "end_date":        config.end_date.isoformat(),
        "tournament_data": data,
    }


def tournament_from_db(row: dict):
    """Deserializa un registro de tournaments en TournamentConfig."""
    from .tournament_models import TournamentConfig
    data = row.get("tournament_data") or {}
    data["id"]         = row["id"]
    data["name"]       = row["name"]
    data["start_date"] = row["start_date"]
    data["end_date"]   = row["end_date"]
    return TournamentConfig.model_validate(data)
