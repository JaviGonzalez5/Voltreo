"""
Genera los enfrentamientos round-robin para cada grupo del ranking.
- Funciona con grupos de cualquier tamaño.
- Evita duplicados.
- Soporta importar partidos ya jugados para excluirlos.
"""

from itertools import combinations
from typing import Optional

from .models import Group, Match, Pair, MatchStatus


def generate_round_robin(group: Group, played_pairs: Optional[set[frozenset[str]]] = None) -> list[Match]:
    """
    Genera todos los enfrentamientos posibles entre parejas de un grupo (round-robin).

    Args:
        group: Grupo con su lista de parejas.
        played_pairs: Conjunto de frozensets de IDs de pareja ya jugados.
                      Si se pasa, esos enfrentamientos se omiten.

    Returns:
        Lista de Match en estado PENDING.
    """
    if played_pairs is None:
        played_pairs = set()

    matches: list[Match] = []
    pairs = group.pairs

    for pair_1, pair_2 in combinations(pairs, 2):
        key = frozenset({pair_1.id, pair_2.id})
        if key in played_pairs:
            continue

        match = Match(
            group_id=group.id,
            group_name=group.name,
            pair_1=pair_1,
            pair_2=pair_2,
            status=MatchStatus.PENDING,
        )
        matches.append(match)

    return matches


def generate_all_matches(
    groups: list[Group],
    played_pairs_by_group: Optional[dict[str, set[frozenset[str]]]] = None,
) -> list[Match]:
    """
    Genera todos los partidos pendientes para una lista de grupos.

    Args:
        groups: Lista de grupos.
        played_pairs_by_group: Dict {group_id: set de frozensets ya jugados}.

    Returns:
        Lista completa de partidos pendientes de todos los grupos.
    """
    if played_pairs_by_group is None:
        played_pairs_by_group = {}

    all_matches: list[Match] = []
    for group in groups:
        played = played_pairs_by_group.get(group.id, set())
        matches = generate_round_robin(group, played)
        all_matches.extend(matches)

    return all_matches


def matches_per_group(matches: list[Match]) -> dict[str, list[Match]]:
    """Agrupa los partidos por group_id."""
    result: dict[str, list[Match]] = {}
    for m in matches:
        result.setdefault(m.group_id, []).append(m)
    return result


def summary(matches: list[Match]) -> dict:
    """Resumen rápido de los partidos generados."""
    by_group = matches_per_group(matches)
    return {
        "total_matches": len(matches),
        "groups": {
            gid: len(ms) for gid, ms in by_group.items()
        },
    }
