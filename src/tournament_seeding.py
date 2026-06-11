"""
Asignación automática de cabezas de serie en torneos basada en ELO de TORNEOS.

Lógica:
  1. Para cada pareja del torneo, calcular su ELO promedio (media de los 2
     jugadores, usando su `elo_tournament` — el ELO de ranking no influye).
  2. Ordenar parejas por ELO descendente.
  3. Asignar `seed` = 1, 2, 3, … a las top N parejas.
"""

from __future__ import annotations

import logging

from src.db_elo import get_club_ranking, _normalize_name_key
from src.elo_engine import DEFAULT_ELO

log = logging.getLogger(__name__)


def auto_assign_seeds_from_elo(
    pairs: list, club_id: str, num_seeds: int,
) -> dict:
    """
    Asigna `seed` a las top N parejas según su ELO de torneos promedio.

    Args:
        pairs: lista de TournamentPair (se modifica in-place).
        club_id: para buscar ELOs en la BD.
        num_seeds: cuántas cabezas de serie asignar.

    Returns:
        dict: {"assigned": N, "default_elo_used": N, "pair_elos": [(nombre, elo), …]}.
    """
    if not pairs or num_seeds < 1:
        return {"assigned": 0, "default_elo_used": 0, "pair_elos": []}

    # 1) Jugadores del club con su ELO de torneos
    club_players = get_club_ranking(club_id, context="tournament", limit=10000)
    name_to_id = {p["name_key"]: p["id"] for p in club_players}
    elos = {p["id"]: p.get("elo_tournament", DEFAULT_ELO) for p in club_players}

    # 2) ELO promedio de cada pareja
    pair_elos: list[tuple] = []
    default_used = 0
    for pair in pairs:
        p1_key = _normalize_name_key(getattr(pair.player_1, "full_name",
                                             getattr(pair.player_1, "name", "")))
        p2_key = _normalize_name_key(getattr(pair.player_2, "full_name",
                                             getattr(pair.player_2, "name", "")))
        e1 = elos.get(name_to_id.get(p1_key, ""), DEFAULT_ELO)
        e2 = elos.get(name_to_id.get(p2_key, ""), DEFAULT_ELO)
        if name_to_id.get(p1_key) is None:
            default_used += 1
        if name_to_id.get(p2_key) is None:
            default_used += 1
        pair_elos.append((pair, (e1 + e2) / 2))

    # 3) Ordenar y asignar
    pair_elos.sort(key=lambda x: x[1], reverse=True)
    for p in pairs:
        p.seed = None
    n_assign = min(num_seeds, len(pair_elos))
    for i in range(n_assign):
        pair_elos[i][0].seed = i + 1

    return {
        "assigned": n_assign,
        "default_elo_used": default_used,
        "pair_elos": [(p.display_name, int(elo)) for p, elo in pair_elos],
    }
