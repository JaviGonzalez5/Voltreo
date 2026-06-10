"""
Ascensos y descensos entre grupos al cerrar una fase de ranking.

Independiente de Streamlit y de la base de datos.

Modelo: los grupos forman una ESCALERA ordenada (Nivel 1 — Grupo 1 es el más
alto; después Nivel 1 — Grupo 2, …, Nivel 2 — Grupo 1, …). Cada peldaño es un
grupo. Reglas de movimiento (grupo de tamaño típico 6):

  · Grupo intermedio:  1º y 2º suben 1 · los 2 últimos bajan 1.
  · Grupo TOP:         nadie sube. El último baja 2 peldaños; el penúltimo y
                       el antepenúltimo bajan 1.
  · Grupo bajo el TOP: suben 3 (1º, 2º y 3º) para cubrir las 3 vacantes del
                       top; solo baja 1 (el último).
  · Grupo FONDO:       nadie baja. El 1º sube 2 peldaños; el 2º y el 3º suben 1.
  · Grupo sobre FONDO: bajan 3 (los 3 últimos); solo sube 1 (el 1º).

Con tamaño uniforme, estas reglas conservan el tamaño de todos los grupos.
El plan es una PROPUESTA: la UI permite ajustar destinos antes de confirmar
(altas/bajas de parejas entre fases son normales).
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import RankingPhase, Group, Pair
from .ranking_scorer import ScoringRules, standings_by_group


# ---------------------------------------------------------------------------
# Escalera de grupos
# ---------------------------------------------------------------------------

def ladder_sort_key(group_name: str) -> tuple:
    """Posición del grupo en la escalera a partir de su nombre.
    'Nivel 2 — Grupo 3' → (2, 3). Sin nivel/grupo reconocible va al final."""
    g = group_name or ""
    m_lvl = re.search(r"nivel\s*(\d+)", g, re.I)
    m_grp = re.search(r"grupo\s*(\d+)", g, re.I)
    lvl = int(m_lvl.group(1)) if m_lvl else 9999
    grp = int(m_grp.group(1)) if m_grp else 9999
    return (lvl, grp, g)


def ordered_ladder(groups: list[Group]) -> list[Group]:
    """Grupos ordenados de más alto (índice 0) a más bajo."""
    return sorted(groups, key=lambda g: ladder_sort_key(g.name))


# ---------------------------------------------------------------------------
# Plan de movimientos
# ---------------------------------------------------------------------------

@dataclass
class Movement:
    pair_id: str
    pair_name: str
    from_group: str           # nombre del grupo actual
    to_group: str             # nombre del grupo destino (== from_group si se mantiene)
    position: int             # posición final en su grupo (1 = primero)
    delta: int = 0            # peldaños: -1/-2 sube, +1/+2 baja, 0 se mantiene


@dataclass
class MovementPlan:
    movements: list[Movement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def by_pair(self) -> dict[str, Movement]:
        return {m.pair_id: m for m in self.movements}


def _group_positions(phase: RankingPhase, group: Group) -> list[Pair]:
    """Parejas del grupo ordenadas por clasificación final (1º primero).
    Sin resultados, mantiene el orden de importación."""
    results = [r for r in (getattr(phase, "match_results", []) or [])
               if any(p.id in (r.pair_1_id, r.pair_2_id) for p in group.pairs)]
    if not results:
        return list(group.pairs)
    rules = getattr(phase, "scoring_rules", None) or ScoringRules()
    names = {p.id: p.display_name for p in group.pairs}
    pair_group = {p.id: group.id for p in group.pairs}
    table = standings_by_group(results, names, rules, pair_group).get(group.id, [])
    order = {s.pair_id: i for i, s in enumerate(table)}
    return sorted(group.pairs, key=lambda p: order.get(p.id, 999))


def build_movement_plan(phase: RankingPhase) -> MovementPlan:
    """Calcula la propuesta de ascensos/descensos para todos los grupos."""
    plan = MovementPlan()
    ladder = ordered_ladder(phase.groups)
    n = len(ladder)
    if n == 0:
        return plan
    names = [g.name for g in ladder]

    # Resultados incompletos → avisar (el plan usa la clasificación actual)
    total_results = len([r for r in (getattr(phase, "match_results", []) or [])
                         if r.is_played])
    if total_results == 0 and n > 1:
        plan.warnings.append(
            "No hay resultados registrados: el plan mantiene el orden de "
            "importación de cada grupo."
        )

    def _delta_for(i: int, pos: int, size: int) -> int:
        """Peldaños a mover para la pareja en posición pos (1-based) del grupo i."""
        if n == 1:
            return 0
        if n == 2:
            # Escalera mínima: intercambio simple 2 arriba / 2 abajo
            if i == 0:
                return +1 if pos >= size - 1 else 0
            return -1 if pos <= 2 else 0
        if i == 0:                      # TOP: bajan 3 (último 2 peldaños)
            if pos == size:
                return +2 if n >= 3 else +1
            if pos >= size - 2:
                return +1
            return 0
        if i == n - 1:                  # FONDO: suben 3 (1º dos peldaños)
            if pos == 1:
                return -2 if n >= 3 else -1
            if pos <= 3:
                return -1
            return 0
        if i == 1:                      # bajo el TOP: suben 3, baja 1
            if pos <= 3:
                return -1
            if pos == size:
                return +1
            return 0
        if i == n - 2:                  # sobre el FONDO: sube 1, bajan 3
            if pos == 1:
                return -1
            if pos >= size - 2:
                return +1
            return 0
        # Intermedio estándar: 2 suben, 2 bajan
        if pos <= 2:
            return -1
        if pos >= size - 1:
            return +1
        return 0

    for i, g in enumerate(ladder):
        ordered = _group_positions(phase, g)
        size = len(ordered)
        if size < 4:
            plan.warnings.append(
                f"Grupo '{g.name}' tiene solo {size} pareja(s): revisa sus "
                "movimientos manualmente."
            )
        for pos, pair in enumerate(ordered, 1):
            delta = _delta_for(i, pos, size) if size >= 4 else 0
            target_idx = min(max(i + delta, 0), n - 1)
            plan.movements.append(Movement(
                pair_id=pair.id,
                pair_name=pair.display_name,
                from_group=g.name,
                to_group=names[target_idx],
                position=pos,
                delta=target_idx - i,
            ))

    # Comprobación de conservación de tamaños (aviso, no error)
    from collections import Counter
    sizes_before = Counter(m.from_group for m in plan.movements)
    sizes_after = Counter(m.to_group for m in plan.movements)
    for name in names:
        if sizes_before.get(name, 0) != sizes_after.get(name, 0):
            plan.warnings.append(
                f"Tras los movimientos, '{name}' pasaría de "
                f"{sizes_before.get(name, 0)} a {sizes_after.get(name, 0)} parejas. "
                "Ajusta destinos en la revisión."
            )
    return plan


# ---------------------------------------------------------------------------
# Aplicar el plan → grupos de la fase siguiente
# ---------------------------------------------------------------------------

def _fresh_pair(pair: Pair) -> Pair:
    """Copia de la pareja para la nueva fase: conserva identidad y
    disponibilidad/pista fija; resetea la asignación de grupo."""
    data = pair.model_dump()
    data["group_id"] = None
    return Pair.model_validate(data)


def apply_movement_plan(
    phase: RankingPhase,
    plan: MovementPlan,
    overrides: Optional[dict[str, str]] = None,
) -> list[Group]:
    """
    Construye los grupos de la fase siguiente aplicando el plan.

    overrides: {pair_id: nombre_grupo_destino} — ajustes manuales de la revisión
    (tiene prioridad sobre el plan). Las parejas cuyo destino sea "" o None se
    consideran BAJA y no se incluyen.
    """
    overrides = overrides or {}
    ladder = ordered_ladder(phase.groups)
    pair_lookup = {p.id: p for g in phase.groups for p in g.pairs}

    new_groups: dict[str, Group] = {
        g.name: Group(name=g.name, level=g.level, gender=g.gender, pairs=[])
        for g in ladder
    }
    valid_names = set(new_groups)

    for mv in plan.movements:
        target = overrides.get(mv.pair_id, mv.to_group)
        if not target:
            continue  # baja voluntaria
        if target not in valid_names:
            target = mv.from_group if mv.from_group in valid_names else None
            if target is None:
                continue
        pair = pair_lookup.get(mv.pair_id)
        if pair is None:
            continue
        new_pair = _fresh_pair(pair)
        new_pair.group_id = new_groups[target].id
        new_groups[target].pairs.append(new_pair)

    return [new_groups[g.name] for g in ladder]
