"""Tests del generador de enfrentamientos round-robin."""
import pytest
from itertools import combinations

from src.models import Group, Pair, Player
from src.ranking_generator import generate_round_robin, generate_all_matches, summary


def make_pair(name: str, group_id: str = "g1") -> Pair:
    parts = name.split(" / ")
    p1 = Player(name=parts[0])
    p2 = Player(name=parts[1] if len(parts) > 1 else "B")
    return Pair(name=name, player_1=p1, player_2=p2, group_id=group_id)


def make_group(n_pairs: int, group_id: str = "g1") -> Group:
    pairs = [make_pair(f"P{i+1} / P{i+1}b", group_id) for i in range(n_pairs)]
    return Group(id=group_id, name=f"Grupo {group_id}", pairs=pairs)


class TestGenerateRoundRobin:
    def test_6_pairs_produces_15_matches(self):
        group = make_group(6)
        matches = generate_round_robin(group)
        assert len(matches) == 15  # C(6,2) = 15

    def test_4_pairs_produces_6_matches(self):
        group = make_group(4)
        matches = generate_round_robin(group)
        assert len(matches) == 6  # C(4,2) = 6

    def test_2_pairs_produces_1_match(self):
        group = make_group(2)
        matches = generate_round_robin(group)
        assert len(matches) == 1

    def test_no_duplicate_matchups(self):
        group = make_group(6)
        matches = generate_round_robin(group)
        seen = set()
        for m in matches:
            key = frozenset({m.pair_1.id, m.pair_2.id})
            assert key not in seen, "Partido duplicado detectado"
            seen.add(key)

    def test_all_matches_belong_to_group(self):
        group = make_group(5, group_id="g99")
        matches = generate_round_robin(group)
        for m in matches:
            assert m.group_id == "g99"

    def test_skip_played_pairs(self):
        group = make_group(4)
        pair_ids = [p.id for p in group.pairs]
        # Marcamos el primer enfrentamiento como ya jugado
        played = {frozenset({pair_ids[0], pair_ids[1]})}
        matches = generate_round_robin(group, played_pairs=played)
        assert len(matches) == 5  # C(4,2) - 1 = 5

    def test_status_is_pending(self):
        from src.models import MatchStatus
        group = make_group(3)
        matches = generate_round_robin(group)
        for m in matches:
            assert m.status == MatchStatus.PENDING


class TestGenerateAllMatches:
    def test_multiple_groups(self):
        groups = [make_group(6, f"g{i}") for i in range(3)]
        matches = generate_all_matches(groups)
        assert len(matches) == 3 * 15  # 3 grupos × 15 partidos

    def test_summary_structure(self):
        groups = [make_group(4, "gA"), make_group(6, "gB")]
        matches = generate_all_matches(groups)
        s = summary(matches)
        assert s["total_matches"] == 6 + 15
        assert "gA" in s["groups"]
        assert "gB" in s["groups"]
