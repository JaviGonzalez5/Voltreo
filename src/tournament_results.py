"""
Registro de resultados y avance automático del cuadro de torneo.

Independiente de Streamlit y de la base de datos.

El cuadro se enlaza por (ronda, match_number):
  - Ganador de la ronda R, partido N → ronda siguiente, partido ceil(N/2),
    ocupando el slot pair_1 si N es impar, pair_2 si N es par.
  - Perdedores de Semifinal → partido de 3er/4º puesto (si existe).
"""

from dataclasses import dataclass, field
from math import ceil
from typing import Optional

from .tournament_models import (
    TournamentConfig, TournamentMatch, TournamentPair, MatchRound, TMatchStatus,
)


# Secuencia de rondas del cuadro principal (excluye GROUP y THIRD_PLACE)
_MAIN_SEQUENCE = [
    MatchRound.ROUND_OF_16,
    MatchRound.QUARTERFINAL,
    MatchRound.SEMIFINAL,
    MatchRound.FINAL,
]


def _next_round(r: MatchRound) -> Optional[MatchRound]:
    """Ronda siguiente en el cuadro principal, o None si es la final."""
    if r not in _MAIN_SEQUENCE:
        return None
    idx = _MAIN_SEQUENCE.index(r)
    if idx + 1 < len(_MAIN_SEQUENCE):
        return _MAIN_SEQUENCE[idx + 1]
    return None


def register_result(
    config: TournamentConfig,
    match_id: str,
    winner_id: str,
    score: str = "",
) -> TournamentConfig:
    """
    Registra el resultado de un partido y propaga el ganador (y perdedor de SF)
    al siguiente partido del cuadro. Modifica config in-place y lo devuelve.
    """
    match = next((m for m in config.matches if m.id == match_id), None)
    if match is None:
        raise ValueError(f"Partido no encontrado: {match_id}")

    # Validar que el ganador es uno de los dos rivales
    valid_ids = {p.id for p in (match.pair_1, match.pair_2) if p is not None}
    if winner_id not in valid_ids:
        raise ValueError("El ganador debe ser una de las dos parejas del partido.")

    match.winner_id = winner_id
    match.score = score
    match.status = TMatchStatus.SCHEDULED  # jugado/cerrado

    _propagate(config, match)
    return config


def clear_result(config: TournamentConfig, match_id: str) -> TournamentConfig:
    """Borra el resultado de un partido y limpia las parejas propagadas aguas abajo."""
    match = next((m for m in config.matches if m.id == match_id), None)
    if match is None:
        return config
    match.winner_id = None
    match.score = ""
    # Recalcular todo el cuadro desde cero para limpiar propagaciones
    return recompute_bracket(config)


def _propagate(config: TournamentConfig, match: TournamentMatch) -> None:
    """Lleva el ganador de `match` al partido correspondiente de la ronda siguiente."""
    winner = match.winner_pair
    if winner is None:
        return

    # Partido de grupo: no propaga al cuadro directamente
    if match.round == MatchRound.GROUP:
        return

    nxt = _next_round(match.round)
    if nxt is not None:
        target_num = ceil(match.match_number / 2)
        target = _find_match(config, nxt, target_num, division=match.division)
        if target is not None:
            _set_slot(target, match.match_number, winner)

    # Perdedor de semifinal → 3er/4º puesto (de la misma división)
    if match.round == MatchRound.SEMIFINAL:
        loser = match.loser_pair
        tp = _find_match(config, MatchRound.THIRD_PLACE, 1, division=match.division)
        if tp is not None and loser is not None:
            _set_slot(tp, match.match_number, loser)


def _set_slot(target: TournamentMatch, source_match_number: int, pair: TournamentPair) -> None:
    """Coloca `pair` en el slot 1 (si source impar) o 2 (si source par) del partido destino."""
    if source_match_number % 2 == 1:
        target.pair_1 = pair
        target.pair_1_label = pair.display_name
    else:
        target.pair_2 = pair
        target.pair_2_label = pair.display_name


def _find_match(config: TournamentConfig, rnd: MatchRound, match_number: int,
                division: Optional[str] = None) -> Optional[TournamentMatch]:
    # En torneos multi-categoría, (ronda, match_number) se repite entre divisiones:
    # hay que filtrar por división para no propagar el ganador a otra categoría.
    return next(
        (m for m in config.matches
         if m.round == rnd and m.match_number == match_number
         and (division is None or m.division == division)),
        None,
    )


def _divisions_present(config: TournamentConfig) -> list[Optional[str]]:
    """Lista de claves de división presentes en los partidos (o [None] si no hay)."""
    divs = sorted({m.division for m in config.matches if m.division is not None})
    return divs or [None]


def recompute_bracket(config: TournamentConfig) -> TournamentConfig:
    """
    Recalcula todas las propagaciones del cuadro desde los resultados registrados.
    Se procesa por división para que cada categoría tenga su propio cuadro.
    """
    for div in _divisions_present(config):
        div_matches = [m for m in config.matches
                       if (div is None or m.division == div)]
        bracket_rounds = [r for r in _MAIN_SEQUENCE if any(m.round == r for m in div_matches)]
        if not bracket_rounds:
            continue
        first_round = bracket_rounds[0]

        # Limpiar slots de rondas posteriores a la primera (dentro de la división)
        for m in div_matches:
            if m.round in (MatchRound.GROUP, first_round):
                continue
            if m.round in _MAIN_SEQUENCE or m.round == MatchRound.THIRD_PLACE:
                m.pair_1 = None
                m.pair_2 = None

        # Propagar en orden de rondas
        ordered = sorted(
            [m for m in div_matches if m.round != MatchRound.GROUP],
            key=lambda m: (m.round.order, m.match_number),
        )
        for m in ordered:
            if m.winner_id is not None:
                valid = {p.id for p in (m.pair_1, m.pair_2) if p is not None}
                if m.winner_id in valid:
                    _propagate(config, m)
                else:
                    m.winner_id = None
                    m.score = ""
    return config


# ---------------------------------------------------------------------------
# Resumen / campeón
# ---------------------------------------------------------------------------

def tournament_champion(config: TournamentConfig, division: Optional[str] = None) -> Optional[TournamentPair]:
    """Devuelve el campeón de la división (o del torneo si es de una sola categoría)."""
    final = _find_match(config, MatchRound.FINAL, 1, division=division)
    if final is not None and final.is_played:
        return final.winner_pair
    return None


def champions_by_division(config: TournamentConfig) -> dict[str, Optional[str]]:
    """{clave_division: nombre_campeon|None} para todas las divisiones."""
    out: dict[str, Optional[str]] = {}
    for div in _divisions_present(config):
        champ = tournament_champion(config, division=div)
        out[div or "_"] = champ.display_name if champ else None
    return out


# ---------------------------------------------------------------------------
# Clasificación de la fase de grupos
# ---------------------------------------------------------------------------

@dataclass
class GroupStanding:
    """Fila de clasificación de una pareja dentro de un grupo."""
    pair_id: str
    pair_name: str
    played: int = 0
    won: int = 0
    lost: int = 0
    sets_for: int = 0
    sets_against: int = 0
    games_for: int = 0
    games_against: int = 0

    @property
    def points(self) -> int:
        # Pádel/pickleball sin empates: victoria = 3 puntos.
        return self.won * 3

    @property
    def set_diff(self) -> int:
        return self.sets_for - self.sets_against

    @property
    def game_diff(self) -> int:
        return self.games_for - self.games_against


def _parse_score(score: str) -> Optional[tuple[int, int, int, int]]:
    """
    Parsea un marcador legible ("6-4 6-3", "6-4, 3-6, 10-8") y devuelve
    (sets_p1, sets_p2, games_p1, games_p2). None si no se puede interpretar.
    El lado izquierdo de cada set corresponde a pair_1, el derecho a pair_2.
    """
    if not score or not score.strip():
        return None
    tokens = score.replace(",", " ").split()
    sets_p1 = sets_p2 = games_p1 = games_p2 = 0
    parsed_any = False
    for tok in tokens:
        sep = "-" if "-" in tok else ("/" if "/" in tok else None)
        if sep is None:
            continue
        a_str, _, b_str = tok.partition(sep)
        try:
            a, b = int(a_str.strip()), int(b_str.strip())
        except ValueError:
            continue
        parsed_any = True
        games_p1 += a
        games_p2 += b
        if a > b:
            sets_p1 += 1
        elif b > a:
            sets_p2 += 1
    if not parsed_any:
        return None
    return sets_p1, sets_p2, games_p1, games_p2


def group_standings(
    config: TournamentConfig, division: Optional[str] = None
) -> dict[str, list[GroupStanding]]:
    """
    Calcula la clasificación de cada grupo de la división (o de todo el torneo).

    Devuelve {group_id: [GroupStanding, ...]} ya ordenado por:
    puntos → diferencia de sets → diferencia de juegos → victorias.

    Solo cuenta partidos de la ronda GROUP que estén jugados (con winner_id).
    Si un partido jugado no tiene marcador parseable, cuenta la victoria/derrota
    pero no suma sets ni juegos.
    """
    # Mapa de parejas por grupo (a partir de config.groups; filtrado por división)
    rows: dict[str, dict[str, GroupStanding]] = {}
    group_div: dict[str, Optional[str]] = {}
    for g in config.groups:
        # Una división por grupo: la de sus parejas
        gdiv = next((p.division for p in g.pairs if p.division is not None), None)
        group_div[g.id] = gdiv
        if division is not None and gdiv != division:
            continue
        rows[g.id] = {
            p.id: GroupStanding(pair_id=p.id, pair_name=p.display_name)
            for p in g.pairs
        }

    for m in config.matches:
        if m.round != MatchRound.GROUP or not m.is_played:
            continue
        if m.group_id not in rows:
            continue
        if m.pair_1 is None or m.pair_2 is None:
            continue
        table = rows[m.group_id]
        s1 = table.get(m.pair_1.id)
        s2 = table.get(m.pair_2.id)
        if s1 is None or s2 is None:
            continue

        s1.played += 1
        s2.played += 1
        if m.winner_id == m.pair_1.id:
            s1.won += 1
            s2.lost += 1
        elif m.winner_id == m.pair_2.id:
            s2.won += 1
            s1.lost += 1

        parsed = _parse_score(m.score)
        if parsed is not None:
            sp1, sp2, gp1, gp2 = parsed
            s1.sets_for += sp1; s1.sets_against += sp2
            s2.sets_for += sp2; s2.sets_against += sp1
            s1.games_for += gp1; s1.games_against += gp2
            s2.games_for += gp2; s2.games_against += gp1

    out: dict[str, list[GroupStanding]] = {}
    for gid, table in rows.items():
        out[gid] = sorted(
            table.values(),
            key=lambda s: (s.points, s.set_diff, s.game_diff, s.won),
            reverse=True,
        )
    return out


def results_summary(config: TournamentConfig) -> dict:
    """Resumen de progreso de resultados (global, sumando todas las divisiones)."""
    playable = [m for m in config.matches if m.pair_1 and m.pair_2]
    played   = [m for m in playable if m.is_played]
    divs = _divisions_present(config)
    if len(divs) > 1:
        champ_names = [c for c in champions_by_division(config).values() if c]
        champ = ", ".join(champ_names) if champ_names else None
    else:
        c = tournament_champion(config, division=divs[0])
        champ = c.display_name if c else None
    return {
        "total_playable": len(playable),
        "played": len(played),
        "pending": len(playable) - len(played),
        "champion": champ,
    }
