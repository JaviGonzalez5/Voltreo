"""
Puntuación y clasificación del ranking.

Independiente de Streamlit y de la base de datos.
Convierte resultados de partidos (MatchResult) en una clasificación (Standing)
según unas reglas configurables (ScoringRules).

Para pádel: cada partido es al mejor de N sets; cada set se gana por juegos.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Reglas de puntuación (configurables por club)
# ---------------------------------------------------------------------------

class ScoringRules(BaseModel):
    """Reglas de puntuación de una fase de ranking."""
    points_win:  int = 3      # puntos por victoria
    points_draw: int = 1      # puntos por empate (raro en pádel, pero configurable)
    points_loss: int = 0      # puntos por derrota
    # Bonus opcional: punto extra por ganar sin ceder ningún set
    bonus_clean_sheet: int = 0
    # Orden de desempate: aplicado en este orden
    # "points" → "set_diff" → "game_diff" → "wins" → "head_to_head"
    sets_to_win: int = 2      # sets necesarios para ganar el partido (2 = al mejor de 3)


# ---------------------------------------------------------------------------
# Resultado de un partido
# ---------------------------------------------------------------------------

class SetScore(BaseModel):
    games_1: int = 0    # juegos de la pareja 1
    games_2: int = 0    # juegos de la pareja 2


class MatchResult(BaseModel):
    """Resultado registrado de un partido del ranking."""
    match_id: str
    pair_1_id: str
    pair_2_id: str
    group_id:  Optional[str] = None
    sets: list[SetScore] = Field(default_factory=list)
    # walkover / retirada: si se rellena, gana el indicado sin contar sets
    walkover_winner_id: Optional[str] = None

    @property
    def sets_won_1(self) -> int:
        return sum(1 for s in self.sets if s.games_1 > s.games_2)

    @property
    def sets_won_2(self) -> int:
        return sum(1 for s in self.sets if s.games_2 > s.games_1)

    @property
    def games_won_1(self) -> int:
        return sum(s.games_1 for s in self.sets)

    @property
    def games_won_2(self) -> int:
        return sum(s.games_2 for s in self.sets)

    @property
    def winner_id(self) -> Optional[str]:
        """ID de la pareja ganadora, o None si empate / sin jugar."""
        if self.walkover_winner_id:
            return self.walkover_winner_id
        if not self.sets:
            return None
        if self.sets_won_1 > self.sets_won_2:
            return self.pair_1_id
        if self.sets_won_2 > self.sets_won_1:
            return self.pair_2_id
        return None  # empate en sets

    @property
    def is_played(self) -> bool:
        return bool(self.sets) or bool(self.walkover_winner_id)


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------

class Standing(BaseModel):
    """Fila de clasificación de una pareja."""
    pair_id: str
    pair_name: str = ""
    group_id: Optional[str] = None
    played: int = 0
    won:    int = 0
    drawn:  int = 0
    lost:   int = 0
    sets_for:     int = 0
    sets_against: int = 0
    games_for:     int = 0
    games_against: int = 0
    points: int = 0

    @property
    def set_diff(self) -> int:
        return self.sets_for - self.sets_against

    @property
    def game_diff(self) -> int:
        return self.games_for - self.games_against


# ---------------------------------------------------------------------------
# Cálculo de clasificación
# ---------------------------------------------------------------------------

def compute_standings(
    results: list[MatchResult],
    pair_names: dict[str, str],
    rules: ScoringRules,
    pair_group: Optional[dict[str, str]] = None,
) -> list[Standing]:
    """
    Calcula la clasificación a partir de los resultados.

    Args:
        results:    lista de MatchResult (jugados o no — los no jugados se ignoran)
        pair_names: {pair_id: nombre legible}
        rules:      reglas de puntuación
        pair_group: {pair_id: group_id} opcional, para agrupar la clasificación

    Returns:
        Lista de Standing ordenada de mejor a peor (aplicando desempates).
    """
    pair_group = pair_group or {}
    table: dict[str, Standing] = {}

    def _row(pair_id: str) -> Standing:
        if pair_id not in table:
            table[pair_id] = Standing(
                pair_id=pair_id,
                pair_name=pair_names.get(pair_id, pair_id),
                group_id=pair_group.get(pair_id),
            )
        return table[pair_id]

    # Asegurar que todas las parejas conocidas aparecen aunque no hayan jugado
    for pid in pair_names:
        _row(pid)

    for r in results:
        if not r.is_played:
            continue
        s1 = _row(r.pair_1_id)
        s2 = _row(r.pair_2_id)

        s1.played += 1
        s2.played += 1

        # Walkover: el ganador suma victoria, el otro derrota, sin sets/juegos
        if r.walkover_winner_id:
            win, lose = (s1, s2) if r.walkover_winner_id == r.pair_1_id else (s2, s1)
            win.won += 1
            win.points += rules.points_win
            lose.lost += 1
            lose.points += rules.points_loss
            continue

        # Sets y juegos
        s1.sets_for      += r.sets_won_1
        s1.sets_against  += r.sets_won_2
        s2.sets_for      += r.sets_won_2
        s2.sets_against  += r.sets_won_1
        s1.games_for     += r.games_won_1
        s1.games_against += r.games_won_2
        s2.games_for     += r.games_won_2
        s2.games_against += r.games_won_1

        winner = r.winner_id
        if winner is None:
            # Empate
            s1.drawn += 1
            s2.drawn += 1
            s1.points += rules.points_draw
            s2.points += rules.points_draw
        elif winner == r.pair_1_id:
            s1.won  += 1
            s2.lost += 1
            s1.points += rules.points_win
            s2.points += rules.points_loss
            if rules.bonus_clean_sheet and r.sets_won_2 == 0:
                s1.points += rules.bonus_clean_sheet
        else:
            s2.won  += 1
            s1.lost += 1
            s2.points += rules.points_win
            s1.points += rules.points_loss
            if rules.bonus_clean_sheet and r.sets_won_1 == 0:
                s2.points += rules.bonus_clean_sheet

    standings = list(table.values())

    # Cabeza a cabeza: puntos entre las parejas empatadas
    def _head_to_head(pid_a: str, pid_b: str) -> int:
        """Diferencia de victorias directas entre A y B (>0 si A domina)."""
        bal = 0
        for r in results:
            if not r.is_played:
                continue
            ids = {r.pair_1_id, r.pair_2_id}
            if ids == {pid_a, pid_b}:
                w = r.winner_id
                if w == pid_a:
                    bal += 1
                elif w == pid_b:
                    bal -= 1
        return bal

    # Ordenación con desempates: puntos → dif sets → dif juegos → victorias
    # El head-to-head se aplica como criterio final entre pares.
    import functools

    def _cmp(a: Standing, b: Standing) -> int:
        if a.points != b.points:
            return b.points - a.points
        if a.set_diff != b.set_diff:
            return b.set_diff - a.set_diff
        if a.game_diff != b.game_diff:
            return b.game_diff - a.game_diff
        if a.won != b.won:
            return b.won - a.won
        h2h = _head_to_head(a.pair_id, b.pair_id)
        if h2h != 0:
            return -h2h  # si a domina (h2h>0), a va primero (return negativo)
        # Estable por nombre para resultado determinista
        return (a.pair_name > b.pair_name) - (a.pair_name < b.pair_name)

    standings.sort(key=functools.cmp_to_key(_cmp))
    return standings


def standings_by_group(
    results: list[MatchResult],
    pair_names: dict[str, str],
    rules: ScoringRules,
    pair_group: dict[str, str],
) -> dict[str, list[Standing]]:
    """
    Devuelve la clasificación separada por grupo: {group_id: [Standing, ...]}.
    """
    all_standings = compute_standings(results, pair_names, rules, pair_group)
    by_group: dict[str, list[Standing]] = {}
    for s in all_standings:
        gid = s.group_id or "_sin_grupo"
        by_group.setdefault(gid, []).append(s)
    return by_group
