"""
Generación de la estructura de un torneo (grupos y/o cuadro).

Funciones principales:
  - generate_tournament_structure(config) → TournamentConfig con groups y matches rellenos
  - assign_seeds(pairs, n_seeds) → lista con cabezas de serie asignadas
"""

from math import ceil
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
# Recomendación de estructura (IA heurística)
# ---------------------------------------------------------------------------

def recommend_structure(n_pairs: int) -> dict:
    """
    Recomienda una estructura de torneo razonable según el nº de parejas.

    Heurística: grupos de 3-4 parejas (lo ideal en pádel/pickleball para que
    todos jueguen varios partidos sin alargar demasiado), clasifican los 2
    primeros de cada grupo, y la fase final es la mayor potencia de 2 que cabe
    en los clasificados.

    Devuelve: {num_groups, group_size_aprox, qualifiers, bracket_size,
               bracket_label, reason}
    """
    if n_pairs < 2:
        return {
            "num_groups": 1, "group_size_aprox": n_pairs, "qualifiers": 1,
            "bracket_size": 0, "bracket_label": "Sin partidos",
            "reason": "Hacen falta al menos 2 parejas.",
        }

    if n_pairs <= 3:
        return {
            "num_groups": 1, "group_size_aprox": n_pairs, "qualifiers": 2,
            "bracket_size": 2, "bracket_label": "Solo final",
            "reason": f"Con {n_pairs} parejas, una liguilla y final entre los 2 primeros.",
        }

    # Menor nº de grupos tal que el grupo más grande tenga como máximo 4 parejas
    # (grupos de 3-4 es lo ideal: varios partidos por pareja sin alargar demasiado).
    num_groups = 1
    while ceil(n_pairs / num_groups) > 4:
        num_groups += 1
    qualifiers = 2
    total_q = num_groups * qualifiers

    # Mayor potencia de 2 <= total_q, acotada a [2, 16]
    bs = 1 << (total_q.bit_length() - 1) if total_q >= 2 else 2
    bs = max(2, min(bs, 16))

    labels = {2: "Solo final", 4: "Semifinales + final",
              8: "Cuartos + semis + final", 16: "Dieciseisavos en adelante"}
    base = n_pairs // num_groups
    extra = n_pairs % num_groups
    dist = f"{extra}×{base+1} y {num_groups-extra}×{base}" if extra else f"{num_groups}×{base}"
    return {
        "num_groups": num_groups,
        "group_size_aprox": base,
        "qualifiers": qualifiers,
        "bracket_size": bs,
        "bracket_label": labels.get(bs, f"Cuadro de {bs}"),
        "reason": f"{n_pairs} parejas → {num_groups} grupos ({dist}), "
                  f"clasifican 2 por grupo → {labels.get(bs, bs)}.",
    }


def group_sizes_for(n_pairs: int, num_groups: int) -> list[int]:
    """Reparto de parejas por grupo (los primeros grupos reciben una extra)."""
    if num_groups < 1:
        num_groups = 1
    base  = n_pairs // num_groups
    extra = n_pairs % num_groups
    return [base + 1] * extra + [base] * (num_groups - extra)


def preview_match_counts(
    group_sizes: list[int],
    final_phase: int,
    third_place: bool = False,
    qualifiers: int = 2,
) -> dict:
    """
    Partidos previstos para UNA división, replicando la lógica del generador
    (incluido el recorte del cuadro por clasificados disponibles).

    Args:
        group_sizes: tamaño de cada grupo (round-robin).
        final_phase: cuadro pedido (0=liguilla, 2, 4, 8, 16). 0 = sin eliminatoria.
        third_place: si hay partido de 3er/4º puesto (solo con cuadro ≥ 4).
        qualifiers:  clasificados por grupo (por defecto 2).

    Devuelve: {group_matches, per_group, final_matches, effective_bracket, total}.
    """
    per_group      = [s * (s - 1) // 2 for s in group_sizes]  # C(s,2)
    group_matches  = sum(per_group)
    final_matches  = 0
    effective_bracket = 0
    if final_phase >= 2 and group_sizes:
        safe_q = max(1, min(qualifiers, min(group_sizes)))
        n_qual = len(group_sizes) * safe_q
        if n_qual >= 2:
            max_bs = 1 << (n_qual.bit_length() - 1)   # mayor potencia de 2 ≤ n_qual
            effective_bracket = min(max(2, final_phase), max_bs)
            final_matches = effective_bracket - 1     # eliminatoria de B = B-1 partidos
            # El generador solo crea 3er/4º puesto cuando la primera ronda del
            # cuadro es la semifinal, es decir con un cuadro de exactamente 4.
            if third_place and effective_bracket == 4:
                final_matches += 1
    return {
        "group_matches":     group_matches,
        "per_group":         per_group,
        "final_matches":     final_matches,
        "effective_bracket": effective_bracket,
        "total":             group_matches + final_matches,
    }


def expected_total_matches(config) -> Optional[int]:
    """
    Total de partidos que el torneo DEBERÍA generar según su estructura
    (grupos round-robin + fase final por categoría), replicando al generador.

    Devuelve None si la estructura no está suficientemente configurada como
    para estimarlo con fiabilidad (p.ej. sin nº de grupos definido).
    """
    from .tournament_models import TournamentFormat

    draws = list(getattr(config, "division_draws", []) or [])
    if not draws:
        return None

    total = 0
    for d in draws:
        n_pairs    = len(getattr(d, "pairs", []) or [])
        num_groups = int(getattr(d, "num_groups", 0) or 0)
        if n_pairs < 2:
            continue
        if num_groups <= 0:
            return None  # estructura incompleta → no estimar
        fmt = getattr(d, "format", None)
        if fmt == TournamentFormat.GROUPS:
            final_phase = 0
        else:
            final_phase = int(getattr(d, "bracket_size", 0) or 0)
        total += preview_match_counts(
            group_sizes_for(n_pairs, num_groups),
            final_phase,
            third_place=bool(getattr(d, "third_place_match", False)),
            qualifiers=int(getattr(d, "groups_qualifiers", 2) or 2),
        )["total"]
    return total


# ---------------------------------------------------------------------------
# Reparto en grupos
# ---------------------------------------------------------------------------

def _make_groups(
    pairs: list[TournamentPair],
    group_size: int,
    num_groups: int = 0,
) -> list[TournamentGroup]:
    """
    Divide las parejas en grupos.

    - Si `num_groups` > 0: crea exactamente ese número de grupos y reparte las
      parejas equitativamente (ej. 11 parejas en 4 grupos → 3,3,3,2).
    - Si no: deriva el número de grupos a partir de `group_size`
      (el último grupo puede quedar más pequeño).

    Las cabezas de serie (seed=1, 2, …) se reparten un grupo cada una; el resto
    se asigna rellenando los grupos más vacíos primero.
    """
    n = len(pairs)

    # ── Asignación manual: si alguna pareja tiene assigned_group, respetar ──
    _manual = [p for p in pairs if getattr(p, "assigned_group", None) is not None]
    if _manual:
        # Nº de grupos = el solicitado, o el máximo índice asignado + 1
        max_idx = max(p.assigned_group for p in _manual)
        n_groups = max(num_groups if num_groups > 0 else 0, max_idx + 1, 1)
        groups = [
            TournamentGroup(id=str(uuid4()), name=_group_name(i), pairs=[])
            for i in range(n_groups)
        ]
        # Colocar las asignadas en su grupo
        for p in _manual:
            gi = min(p.assigned_group, n_groups - 1)
            p.group_id = groups[gi].id
            groups[gi].pairs.append(p)
        # Repartir las no asignadas en los grupos más vacíos
        for p in [x for x in pairs if getattr(x, "assigned_group", None) is None]:
            target = min(groups, key=lambda g: len(g.pairs))
            p.group_id = target.id
            target.pairs.append(p)
        return [g for g in groups if g.pairs]

    if num_groups and num_groups > 0:
        n_groups = max(1, min(num_groups, n))
    else:
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
# Round-robin scheduling (circle method)
# ---------------------------------------------------------------------------

def _round_robin_rounds(n: int) -> list[list[tuple[int, int]]]:
    """
    Devuelve las rondas de un round-robin usando el algoritmo de la ruleta.

    Con N parejas (N par) hay N-1 rondas, cada una con N/2 partidos.
    Con N impar se añade un BYE (None) y los partidos contra BYE se omiten.

    Retorna: [ [(i,j), ...], ... ]  — índices en la lista de parejas.
    """
    teams = list(range(n))
    if n % 2 == 1:
        teams.append(None)   # BYE
    half = len(teams) // 2
    rounds: list[list[tuple[int, int]]] = []
    for _ in range(len(teams) - 1):
        round_pairs = []
        for k in range(half):
            t1 = teams[k]
            t2 = teams[len(teams) - 1 - k]
            if t1 is not None and t2 is not None:
                round_pairs.append((t1, t2))
        rounds.append(round_pairs)
        # Rotar: el primer elemento es fijo, los demás rotan
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


# ---------------------------------------------------------------------------
# Generación de partidos de grupos (en orden de rondas)
# ---------------------------------------------------------------------------

def _generate_group_matches(groups: list[TournamentGroup]) -> list[TournamentMatch]:
    """
    Round-robin completo para cada grupo usando el algoritmo de la ruleta.

    Los partidos se generan en orden de RONDAS (no en orden de parejas):
      Ronda 1: P1 vs P4, P2 vs P3  ← todas las parejas juegan a la vez
      Ronda 2: P1 vs P3, P4 vs P2
      Ronda 3: P1 vs P2, P3 vs P4

    Esto permite al scheduler asignarlos en paralelo (una pista por partido
    dentro de cada ronda), distribuyendo la carga de forma equitativa y
    evitando que una pareja juegue varios partidos seguidos mientras otra espera.
    """
    # Generar todos los grupos en sus rondas, luego intercalar ronda a ronda
    # para que el scheduler reciba los partidos de la ronda 1 de todos los
    # grupos antes que los de la ronda 2.
    per_group_rounds: list[list[list[tuple]]] = []
    for group in groups:
        n = len(group.pairs)
        rounds = _round_robin_rounds(n)
        per_group_rounds.append([(group, round_pairs) for round_pairs in rounds])

    # max_rounds = máximo número de rondas entre todos los grupos
    max_rounds = max((len(gr) for gr in per_group_rounds), default=0)

    matches: list[TournamentMatch] = []
    global_match_num = 1

    for round_idx in range(max_rounds):
        for group_rounds in per_group_rounds:
            if round_idx >= len(group_rounds):
                continue
            group, round_pairs = group_rounds[round_idx]
            for (i, j) in round_pairs:
                p1 = group.pairs[i]
                p2 = group.pairs[j]
                matches.append(
                    TournamentMatch.model_construct(
                        id=str(uuid4()),
                        round=MatchRound.GROUP,
                        match_number=global_match_num,
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
                global_match_num += 1
    return matches


# ---------------------------------------------------------------------------
# Generación del cuadro eliminatorio
# ---------------------------------------------------------------------------

def _bracket_round_for_size(bracket_size: int) -> MatchRound:
    """Devuelve la ronda inicial del cuadro según su tamaño."""
    return {
        2:  MatchRound.FINAL,        # solo final (2 mejores)
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
    assert bracket_size in (2, 4, 8, 16), "bracket_size debe ser 2, 4, 8 o 16"

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

def _generate_one_division(
    pairs: list[TournamentPair],
    fmt: TournamentFormat,
    group_size: int,
    groups_qualifiers: int,
    bracket_size: int,
    third_place_match: bool,
    num_groups: int = 0,
) -> "tuple[list[TournamentGroup], list[TournamentMatch], int]":
    """
    Genera (grupos, partidos, bracket_size_efectivo) para UN conjunto de parejas
    según el formato. Lógica común reutilizada por torneos de una o varias
    categorías. No muta ningún config.

    `num_groups` > 0 fuerza ese número exacto de grupos (reparto equitativo).
    """
    groups: list[TournamentGroup] = []
    all_matches: list[TournamentMatch] = []
    eff_bracket = bracket_size

    if fmt == TournamentFormat.GROUPS:
        groups = _make_groups(pairs, group_size, num_groups)
        all_matches = _generate_group_matches(groups)

    elif fmt == TournamentFormat.BRACKET:
        n = min(len(pairs), bracket_size)
        if n < 2:
            return [], [], bracket_size
        bs = max(4, 1 << (n.bit_length() - 1))
        if bs > 16:
            bs = 16
        eff_bracket = bs
        all_matches = _generate_bracket_matches(bs, pairs[:bs], third_place=third_place_match)

    elif fmt == TournamentFormat.GROUPS_BRACKET:
        groups = _make_groups(pairs, group_size, num_groups)
        group_matches = _generate_group_matches(groups)
        _min_group = min((len(g.pairs) for g in groups), default=group_size)
        _safe_q = max(1, min(groups_qualifiers, _min_group))
        n_qualifiers = len(groups) * _safe_q
        if n_qualifiers < 2:
            return groups, group_matches, bracket_size
        # Tamaño del cuadro: el SOLICITADO (2=solo final, 4=semis+final, ...),
        # acotado a la mayor potencia de 2 que cabe en los clasificados disponibles.
        max_bs = 1 << (n_qualifiers.bit_length() - 1)  # potencia de 2 <= n_qualifiers
        bs = min(max(2, bracket_size), max_bs)
        if bs > 16:
            bs = 16
        eff_bracket = bs

        bracket_pairs_tbd: list[TournamentPair] = []
        for g in groups:
            max_rank = min(_safe_q, len(g.pairs))
            for rank in range(1, max_rank + 1):
                bracket_pairs_tbd.append(TournamentPair.model_construct(
                    id=str(uuid4()), name=f"{rank}º {g.name}",
                    player_1=TournamentPlayer_placeholder(g.name, rank),
                    player_2=TournamentPlayer_placeholder(g.name, rank),
                    seed=None, group_id=None,
                ))
                if len(bracket_pairs_tbd) >= bs:
                    break
            if len(bracket_pairs_tbd) >= bs:
                break

        bracket_matches = _generate_bracket_matches(
            bs, bracket_pairs_tbd[:bs], third_place=third_place_match, label_prefix="",
        )
        for bm in bracket_matches:
            bm.pair_1 = None
            bm.pair_2 = None
        all_matches = group_matches + bracket_matches

    return groups, all_matches, eff_bracket


def generate_tournament_structure(config: TournamentConfig) -> TournamentConfig:
    """
    Genera grupos y/o cuadro. Si el torneo tiene varias divisiones
    (config.divisions con >1 categoría), genera una estructura independiente
    por cada división y combina todos los partidos en config.matches.
    De lo contrario, genera un único cuadro como antes.

    Devuelve el mismo objeto `config` modificado in-place.
    """
    div_keys = list(getattr(config, "divisions", []) or [])
    if len(div_keys) > 1:
        return generate_multi_division(config)

    # Config de la única división si se definió en el paso de Parejas
    _single_draw = (config.division_draws or [None])[0]
    _s_num_groups = int(getattr(_single_draw, "num_groups", 0) or 0) if _single_draw else 0
    _s_bracket    = int(getattr(_single_draw, "bracket_size", 0) or 0) if _single_draw else 0
    _s_qualif     = int(getattr(_single_draw, "groups_qualifiers", 0) or 0) if _single_draw else 0
    # Si la división se configuró como liguilla (formato GROUPS), respetarlo
    _s_format     = getattr(_single_draw, "format", None) if _single_draw else None
    _eff_format   = _s_format or config.format

    groups, all_matches, eff_bracket = _generate_one_division(
        list(config.pairs), _eff_format, config.group_size,
        _s_qualif or config.groups_qualifiers,
        _s_bracket or config.bracket_size,
        config.third_place_match,
        num_groups=_s_num_groups,
    )
    config.groups = groups
    config.matches = all_matches
    config.bracket_size = eff_bracket
    # Etiquetar con la división primaria si existe
    _primary = div_keys[0] if div_keys else None
    if _primary:
        for m in all_matches:
            m.division = _primary
    return config


def generate_multi_division(config: TournamentConfig) -> TournamentConfig:
    """
    Genera un cuadro independiente por cada categoría seleccionada.

    Las parejas se reparten por su atributo `division` (clave "cat:sub").
    Cada división produce sus propios grupos/cuadro, etiquetados con la clave.
    `config.matches` y `config.groups` quedan como la UNIÓN de todas — el
    scheduler las planifica sobre las mismas pistas sin solapamientos.
    """
    from .tournament_models import TournamentDivision, TournamentCategory, TournamentSubcategory

    div_keys = list(config.divisions or [])
    # Repartir parejas por división
    pairs_by_div: dict[str, list[TournamentPair]] = {k: [] for k in div_keys}
    for p in config.pairs:
        if p.division in pairs_by_div:
            pairs_by_div[p.division].append(p)

    draws: list[TournamentDivision] = []
    union_groups: list[TournamentGroup] = []
    union_matches: list[TournamentMatch] = []

    # Mapa de configuraciones por división (guardadas desde la UI)
    _div_cfg_map = {d.key: d for d in (config.division_draws or [])}

    for key in div_keys:
        cat_val, _, sub_val = key.partition(":")
        cat = next((c for c in TournamentCategory if c.value == cat_val), None)
        sub = next((s for s in TournamentSubcategory if s.value == sub_val), None)
        d_pairs = pairs_by_div.get(key, [])

        # Usar config por división si existe, si no la global
        _dcfg = _div_cfg_map.get(key)
        _d_group_size       = _dcfg.group_size        if _dcfg else config.group_size
        _d_num_groups       = getattr(_dcfg, "num_groups", 0) if _dcfg else 0
        _d_groups_qualifiers = _dcfg.groups_qualifiers if _dcfg else config.groups_qualifiers
        _d_bracket_size     = _dcfg.bracket_size      if _dcfg else config.bracket_size
        _d_format           = _dcfg.format             if _dcfg else config.format

        groups, matches, eff_bracket = _generate_one_division(
            d_pairs, _d_format, _d_group_size,
            _d_groups_qualifiers, _d_bracket_size, config.third_place_match,
            num_groups=_d_num_groups,
        )
        # Etiquetar todo con la división
        for g in groups:
            for p in g.pairs:
                p.division = key
        for m in matches:
            m.division = key

        draws.append(TournamentDivision(
            key=key, category=cat, subcategory=sub,
            format=_d_format, group_size=_d_group_size, num_groups=_d_num_groups,
            groups_qualifiers=_d_groups_qualifiers, bracket_size=eff_bracket,
            third_place_match=config.third_place_match,
            pairs=d_pairs, groups=groups, matches=matches,
        ))
        union_groups.extend(groups)
        union_matches.extend(matches)

    config.division_draws = draws
    config.groups = union_groups
    config.matches = union_matches
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
