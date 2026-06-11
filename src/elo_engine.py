"""
Sistema ELO para Voltreo.

Modelo ELO clásico adaptado al pádel/pickleball de parejas:

  - Cada jugador tiene un ELO individual (default: 1200).
  - El ELO de una pareja = media del ELO de sus 2 jugadores.
  - Tras cada partido jugado, se actualiza el ELO de los 4 jugadores
    según el resultado real vs. esperado.

Por qué ELO y no puntos por victoria:
  - Refleja la fuerza real del rival (ganar al mejor sube más).
  - No depende del nº de partidos jugados (justo entre clubes pequeños/grandes).
  - Convergente y predictivo (sirve para cabezas de serie).

Constantes:
  K_FACTOR:    velocidad de cambio. 32 = clásico (FIDE/USCF para amateurs).
  DEFAULT_ELO: punto de partida para nuevos jugadores.
  ELO_FLOOR:   suelo mínimo (evita ELOs negativos en novatos extremos).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

K_FACTOR = 32
DEFAULT_ELO = 1200
ELO_FLOOR = 800


@dataclass
class EloDelta:
    """Cambio de ELO de un jugador tras un partido."""
    player_id: str
    elo_before: int
    elo_after: int

    @property
    def delta(self) -> int:
        return self.elo_after - self.elo_before


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Probabilidad de que A gane según la fórmula ELO clásica.
    Devuelve un valor entre 0 y 1.
    """
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def compute_match_deltas(
    pair_a_player_ids: tuple[str, str],
    pair_b_player_ids: tuple[str, str],
    elos_before: dict[str, int],
    winner_pair: str,  # "A" o "B"
    k: int = K_FACTOR,
) -> list[EloDelta]:
    """
    Calcula los cambios de ELO de los 4 jugadores tras un partido de parejas.

    Estrategia:
      1. ELO de cada pareja = media de sus 2 jugadores.
      2. Calcular expected score entre las 2 parejas.
      3. Aplicar la fórmula ELO al delta a la PAREJA.
      4. Repartir el delta de la pareja igualitariamente entre sus jugadores.
         (Variante posible: ponderar por contribución, pero requiere datos extra.)

    Args:
        pair_a_player_ids: (p1, p2) IDs de la pareja A.
        pair_b_player_ids: (p1, p2) IDs de la pareja B.
        elos_before: dict {player_id: elo} antes del partido. Si falta,
                     se asume DEFAULT_ELO.
        winner_pair: "A" o "B".
        k: factor K. Default 32.

    Returns:
        Lista de 4 EloDelta (uno por jugador).

    Raises:
        ValueError si winner_pair no es 'A' o 'B'.
    """
    if winner_pair not in ("A", "B"):
        raise ValueError(f"winner_pair debe ser 'A' o 'B', no {winner_pair!r}")

    a_ids = list(pair_a_player_ids)
    b_ids = list(pair_b_player_ids)

    a_elos = [elos_before.get(pid, DEFAULT_ELO) for pid in a_ids]
    b_elos = [elos_before.get(pid, DEFAULT_ELO) for pid in b_ids]

    rating_a = sum(a_elos) / len(a_elos)
    rating_b = sum(b_elos) / len(b_elos)

    exp_a = expected_score(rating_a, rating_b)
    exp_b = 1.0 - exp_a

    score_a = 1.0 if winner_pair == "A" else 0.0
    score_b = 1.0 - score_a

    # Delta de cada pareja (se aplicará a cada jugador)
    delta_a = round(k * (score_a - exp_a))
    delta_b = round(k * (score_b - exp_b))

    deltas: list[EloDelta] = []
    for pid, before in zip(a_ids, a_elos):
        after = max(ELO_FLOOR, before + delta_a)
        deltas.append(EloDelta(player_id=pid, elo_before=before, elo_after=after))
    for pid, before in zip(b_ids, b_elos):
        after = max(ELO_FLOOR, before + delta_b)
        deltas.append(EloDelta(player_id=pid, elo_before=before, elo_after=after))

    return deltas


def seed_order(pairs: list, elos: dict[str, int]) -> list:
    """
    Devuelve la lista de parejas ordenada por ELO descendente (cabezas de serie).

    El primer elemento es el "cabeza de serie 1" (mayor ELO), el segundo
    es el #2, etc.

    Args:
        pairs: lista de objetos `Pair` con `.player_1` y `.player_2`
               (cada uno con `.id`).
        elos: dict {player_id: elo}.

    Returns:
        Lista de parejas ordenada (descendente).
    """
    def _pair_elo(pair) -> float:
        p1_id = getattr(pair.player_1, "id", "") or pair.player_1.name
        p2_id = getattr(pair.player_2, "id", "") or pair.player_2.name
        return (elos.get(p1_id, DEFAULT_ELO) +
                elos.get(p2_id, DEFAULT_ELO)) / 2

    return sorted(pairs, key=_pair_elo, reverse=True)


def assign_seed_numbers(pairs: list, elos: dict[str, int]) -> dict[str, int]:
    """Devuelve {pair_id: seed_number} (1 = el de mayor ELO)."""
    ordered = seed_order(pairs, elos)
    return {p.id: i + 1 for i, p in enumerate(ordered)}
