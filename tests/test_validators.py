"""Tests para src/validators.py — validaciones de grupos y datos."""
import pytest
from src.models import Group, Pair, Player
from src.validators import (
    validate_groups,
    validate_groups_df,
    validate_phase_dates,
    validate_required_text,
    issues_summary,
    EXPECTED_GROUP_SIZE,
)
import pandas as pd
from datetime import date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name: str, email: str | None = None, phone: str | None = None) -> Player:
    return Player(name=name, email=email, phone=phone)


def make_pair(name: str, p1: Player, p2: Player, group_id: str = "g1") -> Pair:
    return Pair(name=name, player_1=p1, player_2=p2, group_id=group_id)


def make_full_group(gid: str = "g1", size: int = EXPECTED_GROUP_SIZE) -> Group:
    """Grupo válido de `size` parejas, todos con contacto."""
    pairs = []
    for i in range(size):
        p1 = make_player(f"Player{i}A", email=f"a{i}@x.com")
        p2 = make_player(f"Player{i}B", phone=f"60000000{i}")
        pairs.append(make_pair(f"Pair{i}", p1, p2, gid))
    return Group(id=gid, name=f"Grupo {gid}", pairs=pairs)


# ---------------------------------------------------------------------------
# validate_groups — grupo correcto
# ---------------------------------------------------------------------------

class TestValidateGroupsOk:
    def test_no_issues_for_valid_group(self):
        g = make_full_group()
        issues = validate_groups([g])
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == [], f"No debería haber errores: {errors}"

    def test_multiple_valid_groups(self):
        groups = [make_full_group(f"g{i}") for i in range(4)]
        issues = validate_groups(groups)
        errors = [i for i in issues if i["severity"] == "error"]
        assert errors == []


# ---------------------------------------------------------------------------
# validate_groups — tamaño del grupo
# ---------------------------------------------------------------------------

class TestValidateGroupSize:
    def test_less_than_2_pairs_is_error(self):
        g = Group(id="g1", name="G1", pairs=[
            make_pair("P1", make_player("A", email="a@x.com"), make_player("B", email="b@x.com"))
        ])
        issues = validate_groups([g])
        assert any(i["severity"] == "error" and "al menos" in i["message"] for i in issues)

    def test_wrong_size_is_warning(self):
        g = make_full_group(size=4)   # 4 != 6
        issues = validate_groups([g])
        assert any(i["severity"] == "warning" and "4 parejas" in i["message"] for i in issues)

    def test_correct_size_no_size_warning(self):
        g = make_full_group(size=EXPECTED_GROUP_SIZE)
        issues = validate_groups([g])
        size_warnings = [i for i in issues if i["severity"] == "warning" and "parejas" in i["message"]]
        assert size_warnings == []


# ---------------------------------------------------------------------------
# validate_groups — jugadores duplicados
# ---------------------------------------------------------------------------

class TestValidateDuplicatePlayers:
    def test_duplicate_player_in_group_is_error(self):
        alice = make_player("Alice", email="a@x.com")
        bob   = make_player("Bob",   email="b@x.com")
        carol = make_player("Carol", email="c@x.com")
        pairs = [
            make_pair("A/B", alice, bob),
            make_pair("A/C", alice, carol),  # Alice aparece dos veces
        ]
        g = Group(id="g1", name="G1", pairs=pairs)
        issues = validate_groups([g])
        errors = [i for i in issues if i["severity"] == "error" and "Alice" in i["message"]]
        assert len(errors) == 1

    def test_same_player_name_different_groups_no_error(self):
        """El mismo nombre en grupos distintos no debe ser error (puede ser homónimo)."""
        alice1 = make_player("Alice", email="a1@x.com")
        alice2 = make_player("Alice", email="a2@x.com")
        g1 = Group(id="g1", name="G1", pairs=[
            make_pair("A/B", alice1, make_player("Bob", email="b@x.com"), "g1")
        ])
        g2 = Group(id="g2", name="G2", pairs=[
            make_pair("A/C", alice2, make_player("Carol", email="c@x.com"), "g2")
        ])
        issues = validate_groups([g1, g2])
        dup_errors = [i for i in issues if "más de una pareja" in i["message"]]
        assert dup_errors == []


# ---------------------------------------------------------------------------
# validate_groups — contactos
# ---------------------------------------------------------------------------

class TestValidateMissingContacts:
    def test_no_contact_generates_info(self):
        p1 = make_player("NoContact1")
        p2 = make_player("NoContact2")
        g = Group(id="g1", name="G1", pairs=[make_pair("P", p1, p2)])
        issues = validate_groups([g])
        infos = [i for i in issues if i["severity"] == "info"]
        assert len(infos) >= 1

    def test_email_only_counts_as_contact(self):
        p1 = make_player("WithEmail", email="x@y.com")
        p2 = make_player("WithPhone", phone="600123456")
        g = make_full_group(size=EXPECTED_GROUP_SIZE)
        # Sobreescribir la primera pareja con jugadores con contacto
        g.pairs[0] = make_pair("P", p1, p2)
        issues = validate_groups([g])
        info_for_pair0 = [
            i for i in issues
            if i["severity"] == "info" and "WithEmail" in i["message"]
        ]
        assert info_for_pair0 == [], "Jugador con email no debería generar info"


# ---------------------------------------------------------------------------
# issues_summary
# ---------------------------------------------------------------------------

class TestIssuesSummary:
    def test_counts_correctly(self):
        issues = [
            {"severity": "error", "message": "e1"},
            {"severity": "error", "message": "e2"},
            {"severity": "warning", "message": "w1"},
            {"severity": "info", "message": "i1"},
        ]
        s = issues_summary(issues)
        assert s == {"errors": 2, "warnings": 1, "infos": 1, "total": 4}

    def test_empty_list(self):
        s = issues_summary([])
        assert s["total"] == 0


# ---------------------------------------------------------------------------
# validate_groups_df
# ---------------------------------------------------------------------------

class TestValidateGroupsDf:
    def test_missing_columns(self):
        df = pd.DataFrame({"group_id": ["g1"], "group_name": ["G1"]})
        errs = validate_groups_df(df)
        assert any("pair_name" in e for e in errs)

    def test_valid_df_no_errors(self):
        df = pd.DataFrame({
            "group_id":    ["g1", "g1"],
            "group_name":  ["Grupo 1", "Grupo 1"],
            "pair_name":   ["A/B", "C/D"],
            "player1_name": ["Alice", "Carol"],
            "player2_name": ["Bob",   "Dave"],
        })
        errs = validate_groups_df(df)
        assert errs == []

    def test_empty_pair_name_flagged(self):
        df = pd.DataFrame({
            "group_id":    ["g1"],
            "group_name":  ["G1"],
            "pair_name":   [""],
            "player1_name": ["A"],
            "player2_name": ["B"],
        })
        errs = validate_groups_df(df)
        assert any("pair_name" in e for e in errs)


# ---------------------------------------------------------------------------
# validate_phase_dates
# ---------------------------------------------------------------------------

class TestValidatePhaseDates:
    def test_valid_dates(self):
        errs = validate_phase_dates(date(2025, 1, 1), date(2025, 6, 1))
        assert errs == []

    def test_start_after_end(self):
        errs = validate_phase_dates(date(2025, 6, 1), date(2025, 1, 1))
        assert len(errs) == 1

    def test_none_dates(self):
        errs = validate_phase_dates(None, None)
        assert len(errs) >= 1


# ---------------------------------------------------------------------------
# validate_required_text
# ---------------------------------------------------------------------------

class TestValidateRequiredText:
    def test_required_text_ok(self):
        assert validate_required_text("Ranking Primavera", "Nombre") == []

    def test_required_text_empty(self):
        errs = validate_required_text("   ", "Nombre")
        assert errs == ["Nombre es obligatorio."]

    def test_required_text_none(self):
        errs = validate_required_text(None, "Nombre")
        assert errs == ["Nombre es obligatorio."]
