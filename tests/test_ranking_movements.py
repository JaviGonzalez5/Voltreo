"""
Tests del motor de ascensos/descensos (src/ranking_movements.py).
"""
from datetime import date, time

from src.models import RankingPhase, Group, Pair, Player
from src.ranking_scorer import MatchResult, SetScore
from src.ranking_generator import generate_all_matches
from src.ranking_movements import (
    ladder_sort_key, ordered_ladder, build_movement_plan, apply_movement_plan,
)


def _pair(n):
    return Pair(name=n, player_1=Player(name=n + "a"), player_2=Player(name=n + "b"),
                available_weekdays=[0, 2], available_from=time(18, 0))


def _phase(groups):
    return RankingPhase(name="F", start_date=date(2026, 6, 1), end_date=date(2026, 7, 1),
                        groups=groups)


def _mk_ladder(n_groups, size=6):
    groups = []
    for i in range(n_groups):
        lvl, grp = divmod(i, 100)  # nombres únicos: Nivel 1 — Grupo i+1
        groups.append(Group(
            name=f"Nivel 1 — Grupo {i + 1}",
            pairs=[_pair(f"G{i + 1}P{j + 1}") for j in range(size)],
        ))
    return groups


def _play_all(phase):
    """Juega todos los partidos: gana siempre la pareja con índice menor
    (P1 > P2 > … dentro de cada grupo) → clasificación = orden de importación."""
    results = []
    for g in phase.groups:
        order = {p.id: k for k, p in enumerate(g.pairs)}
        for m in generate_all_matches([g]):
            win_first = order[m.pair_1.id] < order[m.pair_2.id]
            s = [SetScore(games_1=6, games_2=1), SetScore(games_1=6, games_2=1)] if win_first \
                else [SetScore(games_1=1, games_2=6), SetScore(games_1=1, games_2=6)]
            results.append(MatchResult(match_id=m.id, pair_1_id=m.pair_1.id,
                                       pair_2_id=m.pair_2.id, group_id=g.id, sets=s))
    phase.match_results = results
    return phase


class TestLadderOrder:
    def test_sort_by_nivel_then_grupo(self):
        names = ["Nivel 2 — Grupo 1", "Nivel 1 — Grupo 3", "Nivel 1 — Grupo 1"]
        ordered = sorted(names, key=ladder_sort_key)
        assert ordered == ["Nivel 1 — Grupo 1", "Nivel 1 — Grupo 3", "Nivel 2 — Grupo 1"]


class TestMovementRules:
    def test_middle_group_two_up_two_down(self):
        phase = _play_all(_phase(_mk_ladder(5)))
        plan = build_movement_plan(phase)
        mids = [m for m in plan.movements if m.from_group == "Nivel 1 — Grupo 3"]
        deltas = {m.position: m.delta for m in mids}
        assert deltas[1] == -1 and deltas[2] == -1          # 2 suben
        assert deltas[5] == +1 and deltas[6] == +1          # 2 bajan
        assert deltas[3] == 0 and deltas[4] == 0

    def test_top_group_three_down_last_drops_two(self):
        phase = _play_all(_phase(_mk_ladder(5)))
        plan = build_movement_plan(phase)
        top = {m.position: m for m in plan.movements if m.from_group == "Nivel 1 — Grupo 1"}
        assert all(top[p].delta >= 0 for p in (1, 2, 3))     # nadie sube del top
        assert top[6].delta == +2                            # último baja 2
        assert top[5].delta == +1 and top[4].delta == +1     # penúltimo y antepen. bajan 1

    def test_group_below_top_three_up_one_down(self):
        phase = _play_all(_phase(_mk_ladder(5)))
        plan = build_movement_plan(phase)
        g2 = {m.position: m for m in plan.movements if m.from_group == "Nivel 1 — Grupo 2"}
        assert g2[1].delta == -1 and g2[2].delta == -1 and g2[3].delta == -1
        assert g2[6].delta == +1
        assert g2[4].delta == 0 and g2[5].delta == 0

    def test_bottom_group_three_up_first_climbs_two(self):
        phase = _play_all(_phase(_mk_ladder(5)))
        plan = build_movement_plan(phase)
        bot = {m.position: m for m in plan.movements if m.from_group == "Nivel 1 — Grupo 5"}
        assert bot[1].delta == -2
        assert bot[2].delta == -1 and bot[3].delta == -1
        assert all(bot[p].delta <= 0 for p in (4, 5, 6))     # nadie baja del fondo

    def test_sizes_conserved_in_uniform_ladder(self):
        # Con tamaño uniforme y n>=4, las reglas conservan el tamaño de cada grupo
        for n in (4, 5, 7):
            phase = _play_all(_phase(_mk_ladder(n)))
            plan = build_movement_plan(phase)
            size_warns = [w for w in plan.warnings if "pasaría de" in w]
            assert size_warns == [], f"n={n}: {size_warns}"

    def test_single_group_no_movements(self):
        phase = _play_all(_phase(_mk_ladder(1)))
        plan = build_movement_plan(phase)
        assert all(m.delta == 0 for m in plan.movements)


class TestApplyPlan:
    def test_apply_builds_new_groups_with_same_sizes(self):
        phase = _play_all(_phase(_mk_ladder(5)))
        plan = build_movement_plan(phase)
        new_groups = apply_movement_plan(phase, plan)
        assert [g.name for g in new_groups] == [g.name for g in ordered_ladder(phase.groups)]
        for g in new_groups:
            assert len(g.pairs) == 6

    def test_availability_is_preserved(self):
        phase = _play_all(_phase(_mk_ladder(4)))
        plan = build_movement_plan(phase)
        new_groups = apply_movement_plan(phase, plan)
        some = new_groups[0].pairs[0]
        assert some.available_weekdays == [0, 2]
        assert some.available_from == time(18, 0)

    def test_override_moves_pair_and_drop_removes(self):
        phase = _play_all(_phase(_mk_ladder(4)))
        plan = build_movement_plan(phase)
        # El 3º del grupo 3 (se mantiene por defecto) lo forzamos al grupo 1;
        # el 4º del grupo 3 causa BAJA (destino vacío).
        g3 = [m for m in plan.movements if m.from_group == "Nivel 1 — Grupo 3"]
        keep3 = next(m for m in g3 if m.position == 3)
        keep4 = next(m for m in g3 if m.position == 4)
        new_groups = apply_movement_plan(phase, plan, overrides={
            keep3.pair_id: "Nivel 1 — Grupo 1",
            keep4.pair_id: "",
        })
        by_name = {g.name: g for g in new_groups}
        all_ids = {p.id for g in new_groups for p in g.pairs}
        assert keep3.pair_id in {p.id for p in by_name["Nivel 1 — Grupo 1"].pairs}
        assert keep4.pair_id not in all_ids

    def test_new_pairs_have_fresh_group_assignment(self):
        phase = _play_all(_phase(_mk_ladder(4)))
        plan = build_movement_plan(phase)
        new_groups = apply_movement_plan(phase, plan)
        for g in new_groups:
            for p in g.pairs:
                assert p.group_id == g.id
