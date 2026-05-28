"""
Generación de la estructura de un torneo (grupos y/o cuadro).

Funciones principales:
  - generate_tournament_structure(config) → TournamentConfig con groups y matches rellenos
  - assign_seeds(pairs, n_seeds) → lista con cabezas de serie asignadas
"""

from itertools import combinations
from math import ceil, log2
from uuid import uuid4

from .tournament_models import (
    TournamentConfig,
    TournamentFormat,
    TournamentGroup,
    TournamentMatch,
    TournamentPair,
    MatchRound,
    TMatchStatus,
)


# ---------------------------------------------------------------------------
# Reparto en grupos
# ---------------------------------------------------------------------------

def _make_groups(pairs: list[TournamentPair], group_size: int) -> list[TournamentGroup]:
    """
    Divide las parejas en grupos de `group_size` (el último puede ser más pequeño).

    Las cabezas de serie (seed=1, 2, …) se reparten un grupo cada una; el resto
    se asigna por orden de llegada para mantener el comportamiento predecible.
    """
    n = len(pairs)
    n_groups = max(1, ceil(n / group_size))
    groups: list[TournamentGroup] = [
        TournamentGroup(
            id=str(uuid4()),
            name=_group_name(i),
            pairs=[],
        )
        for i in range(n_groups)
    ]

    # Separar cabezas de serie del resto
    seeded   = sorted([p for p in pairs if p.seed is not None], key=lambda p: p.seed)
    unseeded = [p for p in pairs if p.seed is None]

    # Distribuir cabezas de serie: una por grupo (serpentín)
    for i, sp in enumerate(seeded):
        grp = groups[i % n_groups]
        sp.group_id = grp.id
        grp.pairs.append(sp)

    # Distribuir el resto en orden, rellenando grupos más vacíos primero
    for p in unseeded:
        target = min(groups, key=lambda g: len(g.pairs))
        p.group_id = target.id
        target.pairs.append(p)

    return [g for g in groups if g.pairs]


def _group_name(idx: int) -> str:
    """Genera 'Grupo A', 'Grupo B', … 'Grupo Z', 'Grupo AA', …"""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if idx < 26:
        return f"Grupo {letters[idx]}"
    return f"Grupo {letters[idx // 26 - 1]}{letters[idx % 26]}"


# ---------------------------------------------------------------------------
# Generación de partidos de grupos
# ---------------------------------------------------------------------------

def _generate_group_matches(groups: list[TournamentGroup]) -> list[TournamentMatch]:
    """Round-robin completo para cada grupo."""
    matches: list[TournamentMatch] = []
    for group in groups:
        for i, (p1, p2) in enumerate(combinations(group.pairs, 2), start=1):
            matches.append(
                TournamentMatch.model_construct(
                    id=str(uuid4()),
                    round=MatchRound.GROUP,
                    match_number=i,
                    group_id=group.id,
                    pair_1=p1,
                    pair_2=p2,
                    pair_1_label=p1.display_name,
                    pair_2_label=p2.display_name,
                    status=TMatchStatus.PENDING,
                    match_date=None,
                    start_time=None,
                    end_time=None,
                    court=None,
                    conflict_reason=None,
                )
            )
    return matches


# ---------------------------------------------------------------------------
# Generación del cuadro eliminatorio
# ---------------------------------------------------------------------------

def _bracket_round_for_size(bracket_size: int) -> MatchRound:
    """Devuelve la ronda inicial del cuadro según su tamaño."""
    return {
        4:  MatchRound.SEMIFINAL,
        8:  MatchRound.QUARTERFINAL,
        16: MatchRound.ROUND_OF_16,
    }.get(bracket_size, MatchRound.QUARTERFINAL)


def _generate_bracket_matches(
    bracket_size: int,
    pairs: list[TournamentPair],
    third_place: bool = False,
    label_prefix: str = "",
) -> list[TournamentMatch]:
    """
    Genera los partidos del cuadro eliminatorio.

    `pairs` se usa para los partidos de la primera ronda (si están disponibles).
    El resto de rondas tiene etiquetas TBD ("Ganador X / Perdedor X").

    Emparejamiento estándar (seeds):
        1 vs N, 2 vs N-1, 3 vs N-2, … (cabeza de serie arriba)
    """
    assert bracket_size in (4, 8, 16), "bracket_size debe ser 4, 8 o 16"

    matches: list[TournamentMatch] = []
    first_round = _bracket_round_for_size(bracket_size)

    # ── Primera ronda: emparejar seeds
    seeded = sorted([p for p in pairs if p.seed is not None], key=lambda p: p.seed)
    all_pairs = seeded + [p for p in pairs if p.seed is None]

    n_first = bracket_size // 2    # número de partidos en la primera ronda
    first_round_matches: list[TournamentMatch] = []

    for i in range(n_first):
        p1 = all_pairs[i]   if i < len(all_pairs)       else None
        p2 = all_pairs[bracket_size - 1 - i] if (bracket_size - 1 - i) < len(all_pairs) else None

        lbl1 = (p1.display_name if p1 else f"{label_prefix}Pareja {i + 1}")
        lbl2 = (p2.display_name if p2 else f"{label_prefix}Pareja {bracket_size - i}")

        m = TournamentMatch.model_construct(
            id=str(uuid4()),
            round=first_round,
            match_number=i + 1,
            group_id=None,
            pair_1=p1,
            pair_2=p2,
            pair_1_label=lbl1,
            pair_2_label=lbl2,
            status=TMatchStatus.PENDING,
            match_date=None,
            start_time=None,
            end_time=None,
            court=None,
            conflict_reason=None,
        )
        first_round_matches.append(m)
    matches.extend(first_round_matches)

    # ── Rondas siguientes: etiquetas TBD
    # Orden de rondas desde la primera hasta la Final
    round_sequence = [first_round]
    _next: dict[MatchRound, MatchRound] = {
        MatchRound.ROUND_OF_16:  MatchRound.QUARTERFINAL,
        MatchRound.QUARTERFINAL: MatchRound.SEMIFINAL,
        MatchRound.SEMIFINAL:    MatchRound.FINAL,
    }
    while round_sequence[-1] in _next:
        round_sequence.append(_next[round_sequence[-1]])

    prev_matches = first_round_matches
    for r in round_sequence[1:]:     # skip first_round, already done
        n = len(prev_matches) // 2
        current: list[TournamentMatch] = []
        for i in range(n):
            m1 = prev_matches[i * 2]
            m2 = prev_matches[i * 2 + 1]
            lbl1 = f"Ganador {m1.round.display} {m1.match_number}"
            lbl2 = f"Ganador {m2.round.display} {m2.match_number}"
            m = TournamentMatch.model_construct(
                id=str(uuid4()),
                round=r,
                match_number=i + 1,
                group_id=None,
                pair_1=None,
                pair_2=None,
                pair_1_label=lbl1,
                pair_2_label=lbl2,
                status=TMatchStatus.PENDING,
                match_date=None,
                start_time=None,
                end_time=None,
                court=None,
                conflict_reason=None,
            )
            current.append(m)
        matches.extend(current)
        prev_matches = current

    # ── Partido de 3er y 4º puesto (opcional)
    if third_place and first_round == MatchRound.SEMIFINAL:
        sf_matches = [m for m in matches if m.round == MatchRound.SEMIFINAL]
        if len(sf_matches) >= 2:
            m = TournamentMatch.model_construct(
                id=str(uuid4()),
                round=MatchRound.THIRD_PLACE,
                match_number=1,
                group_id=None,
                pair_1=None,
                pair_2=None,
                pair_1_label=f"Perdedor Semifinal 1",
                pair_2_label=f"Perdedor Semifinal 2",
                status=TMatchStatus.PENDING,
                match_date=None,
                start_time=None,
                end_time=None,
                court=None,
                conflict_reason=None,
            )
            matches.append(m)

    return matches


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def generate_tournament_structure(config: TournamentConfig) -> TournamentConfig:
    """
    Genera grupos y/o cuadro según el formato del torneo y rellena
    `config.groups` y `config.matches`.

    Devuelve el mismo objeto `config` modificado in-place.
    """
    pairs = list(config.pairs)
    all_matches: list[TournamentMatch] = []

    if config.format == TournamentFormat.GROUPS:
        groups = _make_groups(pairs, config.group_size)
        config.groups = groups
        all_matches = _generate_group_matches(groups)

    elif config.format == TournamentFormat.BRACKET:
        config.groups = []
        n = min(len(pairs), config.bracket_size)
        # Ajustar bracket_size a la potencia de 2 inferior o igual a n
        bs = max(4, 1 << (n.bit_length() - 1))  # floor power-of-2
        if bs > 16:
            bs = 16
        config.bracket_size = bs
        all_matches = _generate_bracket_matches(
            bs, pairs[:bs],
            third_place=config.third_place_match,
        )

    elif config.format == TournamentFormat.GROUPS_BRACKET:
        groups = _make_groups(pairs, config.group_size)
        config.groups = groups
        group_matches = _generate_group_matches(groups)

        # Cuadro final: el número de plazas es n_groups × qualifiers_per_group
        n_qualifiers = len(groups) * config.groups_qualifiers
        bs = max(4, 1 << (n_qualifiers.bit_length() - 1))
        if bs > 16:
            bs = 16
        config.bracket_size = bs

        # Etiquetas TBD para el cuadro: "1º Grupo A", "2º Grupo A", …
        bracket_pairs_tbd: list[TournamentPair] = []
        for g in groups:
            for rank in range(1, config.groups_qualifiers + 1):
                fake = TournamentPair.model_construct(
                    id=str(uuid4()),
                    name=f"{rank}º {g.name}",
                    player_1=TournamentPlayer_placeholder(g.name, rank),
                    player_2=TournamentPlayer_placeholder(g.name, rank),
                    seed=None,
                    group_id=None,
                )
                bracket_pairs_tbd.append(fake)
                if len(bracket_pairs_tbd) >= bs:
                    break
            if len(bracket_pairs_tbd) >= bs:
                break

        bracket_matches = _generate_bracket_matches(
            bs, bracket_pairs_tbd[:bs],
            third_place=config.third_place_match,
            label_prefix="",
        )
        # Reemplazar pair_1/pair_2 por None (son TBD hasta que terminen los grupos)
        for bm in bracket_matches:
            bm.pair_1 = None
            bm.pair_2 = None

        all_matches = group_matches + bracket_matches

    config.matches = all_matches
    return config


# ---- Helper interno ----
class TournamentPlayer_placeholder:
    """Placeholder para los jugadores TBD en el cuadro (no es un BaseModel real)."""
    def __init__(self, group_name: str, rank: int):
        self.id   = str(uuid4())
        self.full_name = f"{rank}º {group_name}"
        self.name = self.full_name
        self.surname = ""
        self.email = None
        self.phone = None


# ---------------------------------------------------------------------------
# Resumen rápido
# ---------------------------------------------------------------------------

def tournament_summary(config: TournamentConfig) -> dict:
    """Estadísticas de la estructura del torneo."""
    from collections import Counter
    rounds = Counter(m.round.display for m in config.matches)
    return {
        "total_matches":    len(config.matches),
        "n_groups":         len(config.groups),
        "n_pairs":          len(config.pairs),
        "matches_by_round": dict(rounds),
    }
