"""
Mapeo de los resultados leídos de Syltek (parse_round_results) a los MatchResult
de Voltreo, casando parejas por nombre.

Diseño:
  · Para la CLASIFICACIÓN, Voltreo solo necesita `groups` + `match_results`
    (compute_standings no usa los objetos Match). Por eso aquí construimos
    MatchResult directamente desde los resultados de Syltek + las parejas de
    los grupos importados, sin depender del scheduler de Voltreo.
  · El marcador de Syltek viene SIEMPRE desde la perspectiva de `team_a`
    (pareja de la fila): MatchResult.pair_1 = team_a, games_1 = juegos de team_a.
  · `match_id` = id de reserva de Syltek (estable) → reimportar reemplaza, no duplica.
"""

import re
from uuid import uuid4

from .ranking_scorer import MatchResult, SetScore


def _norm(s: str) -> str:
    """Normaliza un nombre de pareja para casar Syltek↔Voltreo:
    minúsculas, puntos fuera, espacios colapsados."""
    s = (s or "").lower().replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_results_from_round(parsed_groups: list[dict], voltreo_groups: list) -> tuple[list, list]:
    """
    parsed_groups : salida de `parse_round_results` (list[dict] con clave 'results').
    voltreo_groups: list[Group] de Voltreo (cada pair con .id, .display_name, .group_id).

    Devuelve (match_results, unmatched):
      · match_results: list[MatchResult] listos para asignar a phase.match_results.
      · unmatched:     list[str] descripciones de partidos que no se pudieron casar.
    """
    # Índice nombre-normalizado → (pair, group)
    idx: dict[str, tuple] = {}
    for g in voltreo_groups:
        for p in getattr(g, "pairs", []) or []:
            idx[_norm(p.display_name)] = (p, g)

    match_results: list = []
    unmatched: list[str] = []
    seen: set = set()

    for blk in parsed_groups:
        for r in blk.get("results", []):
            a = idx.get(_norm(r["team_a"]))
            b = idx.get(_norm(r["team_b"]))
            if not a or not b:
                _miss = r["team_a"] if not a else r["team_b"]
                unmatched.append(f"{r['team_a']} vs {r['team_b']} — pareja no encontrada: {_miss}")
                continue

            pair_a, grp_a = a
            pair_b, _ = b
            key = frozenset([pair_a.id, pair_b.id])
            if key in seen:
                continue
            seen.add(key)

            sets = [SetScore(games_1=int(x), games_2=int(y)) for x, y in r.get("sets", [])]
            if not sets:
                continue
            match_results.append(MatchResult(
                match_id=r.get("reservation_id") or str(uuid4()),
                pair_1_id=pair_a.id,
                pair_2_id=pair_b.id,
                group_id=getattr(pair_a, "group_id", None) or getattr(grp_a, "id", None),
                sets=sets,
            ))

    return match_results, unmatched
