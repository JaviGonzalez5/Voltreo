"""
Tests para src/tournament_generator.py
Cubre: generación de grupos, round-robin, bracket, GROUPS_BRACKET,
       y los edge-cases que producían crashes (n=0, qualifiers=0, qualifiers>group_size).
"""
import pytest
from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TMatchStatus,
)
from src.tournament_generator import generate_tournament_structure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player(name: str) -> TournamentPlayer:
    return TournamentPlayer(name=name, surname="")


def _pair(name: str) -> TournamentPair:
    return TournamentPair(
        name=name,
        player_1=_player(f"{name}-P1"),
        player_2=_player(f"{name}-P2"),
    )


def _base_config(**kwargs) -> TournamentConfig:
    from datetime import date
    defaults = dict(
        name="Test",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 1),
        format=TournamentFormat.GROUPS,
        group_size=4,
        match_duration_minutes=60,
        rest_between_matches_min=15,
    )
    defaults.update(kwargs)
    return TournamentConfig(**defaults)


def _pairs(n: int) -> list[TournamentPair]:
    return [_pair(f"Pareja {i+1}") for i in range(n)]


# ---------------------------------------------------------------------------
# GRUPOS
# ---------------------------------------------------------------------------

class TestGroupsFormat:

    def test_8_pairs_2_groups_of_4(self):
        cfg = _base_config(pairs=_pairs(8), group_size=4)
        result = generate_tournament_structure(cfg)
        assert len(result.groups) == 2
        for g in result.groups:
            assert len(g.pairs) == 4

    def test_5_pairs_with_group_size_3_creates_2_groups(self):
        cfg = _base_config(pairs=_pairs(5), group_size=3)
        result = generate_tournament_structure(cfg)
        assert len(result.groups) == 2
        # Distribución: 3 + 2
        sizes = sorted(len(g.pairs) for g in result.groups)
        assert sizes == [2, 3]

    def test_round_robin_4_pairs_6_matches(self):
        cfg = _base_config(pairs=_pairs(4), group_size=4)
        result = generate_tournament_structure(cfg)
        assert len(result.matches) == 6  # C(4,2) = 6

    def test_round_robin_3_pairs_3_matches(self):
        cfg = _base_config(pairs=_pairs(3), group_size=3)
        result = generate_tournament_structure(cfg)
        assert len(result.matches) == 3  # C(3,2) = 3

    def test_single_pair_group_no_crash(self):
        """Un grupo de 1 pareja no debe crashear — produce 0 partidos."""
        cfg = _base_config(pairs=_pairs(1), group_size=4)
        result = generate_tournament_structure(cfg)
        # 1 grupo con 1 pareja → 0 partidos
        assert len(result.matches) == 0

    def test_no_pair_plays_itself(self):
        cfg = _base_config(pairs=_pairs(6), group_size=3)
        result = generate_tournament_structure(cfg)
        for m in result.matches:
            if m.pair_1 and m.pair_2:
                assert m.pair_1.id != m.pair_2.id

    def test_all_matches_have_round_group(self):
        from src.tournament_models import MatchRound
        cfg = _base_config(pairs=_pairs(8), group_size=4)
        result = generate_tournament_structure(cfg)
        for m in result.matches:
            assert m.round == MatchRound.GROUP

    def test_all_matches_status_pending(self):
        cfg = _base_config(pairs=_pairs(8), group_size=4)
        result = generate_tournament_structure(cfg)
        for m in result.matches:
            assert m.status == TMatchStatus.PENDING

    def test_seeded_pairs_in_different_groups(self):
        ps = _pairs(8)
        ps[0].seed = 1
        ps[1].seed = 2
        cfg = _base_config(pairs=ps, group_size=4)
        result = generate_tournament_structure(cfg)
        # Seeds 1 y 2 deben estar en grupos distintos
        seed1_group = next(
            g.id for g in result.groups if ps[0].id in {p.id for p in g.pairs}
        )
        seed2_group = next(
            g.id for g in result.groups if ps[1].id in {p.id for p in g.pairs}
        )
        assert seed1_group != seed2_group


# ---------------------------------------------------------------------------
# BRACKET (eliminatoria directa)
# ---------------------------------------------------------------------------

class TestBracketFormat:

    def test_8_pairs_bracket_7_matches(self):
        cfg = _base_config(
            pairs=_pairs(8),
            format=TournamentFormat.BRACKET,
            bracket_size=8,
        )
        result = generate_tournament_structure(cfg)
        # 8-team bracket: QF(4) + SF(2) + F(1) = 7
        assert len(result.matches) == 7

    def test_4_pairs_bracket_3_matches(self):
        cfg = _base_config(
            pairs=_pairs(4),
            format=TournamentFormat.BRACKET,
            bracket_size=4,
        )
        result = generate_tournament_structure(cfg)
        # SF(2) + F(1) = 3
        assert len(result.matches) == 3

    def test_bracket_with_third_place_adds_extra_match(self):
        cfg = _base_config(
            pairs=_pairs(4),
            format=TournamentFormat.BRACKET,
            bracket_size=4,
            third_place_match=True,
        )
        result = generate_tournament_structure(cfg)
        assert len(result.matches) == 4  # SF(2) + 3rd(1) + F(1)

    def test_zero_pairs_no_crash(self):
        """n=0 causaba ValueError: negative shift count — ahora debe retornar sin matches."""
        cfg = _base_config(
            pairs=[],
            format=TournamentFormat.BRACKET,
            bracket_size=8,
        )
        result = generate_tournament_structure(cfg)
        assert result.matches == []

    def test_one_pair_no_crash(self):
        cfg = _base_config(
            pairs=_pairs(1),
            format=TournamentFormat.BRACKET,
            bracket_size=4,
        )
        result = generate_tournament_structure(cfg)
        assert result.matches == []


# ---------------------------------------------------------------------------
# GROUPS + BRACKET
# ---------------------------------------------------------------------------

class TestGroupsBracketFormat:

    def test_8_pairs_2_qualifiers_bracket_matches_exist(self):
        cfg = _base_config(
            pairs=_pairs(8),
            format=TournamentFormat.GROUPS_BRACKET,
            group_size=4,
            groups_qualifiers=2,
            bracket_size=4,
        )
        result = generate_tournament_structure(cfg)
        from src.tournament_models import MatchRound
        group_matches   = [m for m in result.matches if m.round == MatchRound.GROUP]
        bracket_matches = [m for m in result.matches if m.round != MatchRound.GROUP]
        assert len(group_matches) > 0
        assert len(bracket_matches) > 0

    def test_bracket_pairs_are_tbd(self):
        cfg = _base_config(
            pairs=_pairs(8),
            format=TournamentFormat.GROUPS_BRACKET,
            group_size=4,
            groups_qualifiers=2,
        )
        result = generate_tournament_structure(cfg)
        from src.tournament_models import MatchRound
        for m in result.matches:
            if m.round != MatchRound.GROUP:
                assert m.pair_1 is None
                assert m.pair_2 is None

    def test_groups_qualifiers_zero_no_crash(self):
        """groups_qualifiers=0 causaba ValueError — ahora se coerce a 1."""
        cfg = _base_config(
            pairs=_pairs(8),
            format=TournamentFormat.GROUPS_BRACKET,
            group_size=4,
            groups_qualifiers=0,
        )
        result = generate_tournament_structure(cfg)
        assert result is not None

    def test_qualifiers_greater_than_group_size_no_phantom_slots(self):
        """qualifiers > group_size generaba slots imposibles — ahora se limita al tamaño real."""
        cfg = _base_config(
            pairs=_pairs(8),
            format=TournamentFormat.GROUPS_BRACKET,
            group_size=4,
            groups_qualifiers=10,  # imposible: grupos de 4
        )
        result = generate_tournament_structure(cfg)
        # Ningún label_1 o label_2 debe referenciar un puesto > group_size
        from src.tournament_models import MatchRound
        for m in result.matches:
            if m.round != MatchRound.GROUP:
                # pair_1_label debe ser vacío o referirse a posición ≤ group_size
                if m.pair_1_label:
                    num = int(m.pair_1_label[0]) if m.pair_1_label[0].isdigit() else 0
                    assert num <= 4, f"Phantom slot: {m.pair_1_label}"


# ---------------------------------------------------------------------------
# Aislamiento: generate no modifica la config original
# ---------------------------------------------------------------------------

class TestImmutability:

    def test_generate_does_not_mutate_original_pairs(self):
        """generate_tournament_structure trabaja sobre una copia."""
        ps = _pairs(4)
        original_ids = [p.id for p in ps]
        cfg = _base_config(pairs=ps, group_size=4)
        generate_tournament_structure(cfg)
        # IDs originales intactos
        assert [p.id for p in ps] == original_ids
