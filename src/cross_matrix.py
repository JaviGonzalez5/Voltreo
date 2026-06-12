"""
Datos de la "planilla de cruces" de un grupo de ranking (matriz round-robin),
para la vista web y el Excel que replica la plantilla del club.

Reutiliza `compute_standings` (mismo cálculo y desempates que la clasificación de
Voltreo) y añade, por cada cruce, el detalle del partido orientado a cada pareja.

Convención del club (verificada con su Excel "RESULTADOS RANKING FASE 3"):
  · ptos del cruce = puntos del partido: 3 ganar / 1 perder / 0 no jugado
    (rules.points_win / points_loss / points_draw).
  · set = sets ganados por la pareja en ese partido.
  · Por cada set se guardan los juegos (game_a, game_b) desde la perspectiva
    de la pareja de la fila.
  · CLAS = posición tras ordenar por puntos → dif sets → dif juegos → victorias
    → head-to-head (empate total → orden de siembra del grupo).
"""

from .ranking_scorer import compute_standings, MatchResult, ScoringRules


def _match_points(r: MatchResult, pair_id: str, rules: ScoringRules) -> int:
    """Puntos que se lleva `pair_id` en el partido r (3/1/0 con las reglas dadas)."""
    if not r.is_played:
        return 0
    winner = r.winner_id
    if winner is None:
        return rules.points_draw
    return rules.points_win if winner == pair_id else rules.points_loss


def build_group_matrix(group_pairs: list, results: list, rules: ScoringRules) -> dict:
    """
    group_pairs: list[Pair] en orden de siembra (1..N) del grupo.
    results:     list[MatchResult] (de cualquier grupo; se filtra a este).
    rules:       ScoringRules de la fase.

    Devuelve:
      {
        "pairs": [{"id","name","seed"}],            # orden de siembra
        "rows":  {pair_id: {played,won,lost,drawn,points,
                            sets_for,sets_against,games_for,games_against,
                            set_diff,game_diff,clas}},
        "cells": {(a_id,b_id): {"sets":[(ga,gb),...],"sets_won":int,"pts":int}},
      }
    """
    pairs = [{"id": p.id, "name": p.display_name, "seed": i + 1}
             for i, p in enumerate(group_pairs)]
    ids = {p["id"] for p in pairs}
    names = {p["id"]: p["name"] for p in pairs}

    grp_results = [
        r for r in results
        if r.pair_1_id in ids and r.pair_2_id in ids
    ]

    standings = compute_standings(grp_results, names, rules)
    clas = {s.pair_id: i + 1 for i, s in enumerate(standings)}

    rows: dict = {}
    for s in standings:
        rows[s.pair_id] = {
            "played": s.played, "won": s.won, "lost": s.lost, "drawn": s.drawn,
            "points": s.points,
            "sets_for": s.sets_for, "sets_against": s.sets_against,
            "games_for": s.games_for, "games_against": s.games_against,
            "set_diff": s.set_diff, "game_diff": s.game_diff,
            "clas": clas[s.pair_id],
        }

    cells: dict = {}
    for r in grp_results:
        if not r.is_played:
            continue
        a, b = r.pair_1_id, r.pair_2_id
        cells[(a, b)] = {
            "sets": [(s.games_1, s.games_2) for s in r.sets],
            "sets_won": r.sets_won_1,
            "pts": _match_points(r, a, rules),
        }
        cells[(b, a)] = {
            "sets": [(s.games_2, s.games_1) for s in r.sets],
            "sets_won": r.sets_won_2,
            "pts": _match_points(r, b, rules),
        }

    return {"pairs": pairs, "rows": rows, "cells": cells}
