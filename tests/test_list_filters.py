"""
Tests de los filtros y búsqueda de las listas principales (src/list_filters.py).

Cubren búsqueda de texto, filtro de fases por estado, filtro de torneos por
nombre/categoría/estado, filtro de clubs y filtro de usuarios por rol/club.
"""

import pytest

from src.list_filters import (
    ALL,
    filter_by_text,
    filter_phases,
    filter_clubs,
    filter_users,
    filter_tournaments,
    tournament_divisions,
    all_division_keys,
)


# ---------------------------------------------------------------------------
# filter_by_text
# ---------------------------------------------------------------------------

def test_text_empty_query_returns_all():
    rows = [{"name": "A"}, {"name": "B"}]
    assert filter_by_text(rows, "", ["name"]) == rows


def test_text_case_and_space_insensitive():
    rows = [{"name": "Liga Verano"}, {"name": "Otoño"}]
    assert filter_by_text(rows, "  VERANO ", ["name"]) == [{"name": "Liga Verano"}]


def test_text_matches_any_field():
    rows = [{"name": "X", "slug": "padel-madrid"}]
    assert filter_by_text(rows, "madrid", ["name", "slug"]) == rows
    assert filter_by_text(rows, "barcelona", ["name", "slug"]) == []


def test_text_does_not_mutate_input():
    rows = [{"name": "A"}, {"name": "B"}]
    filter_by_text(rows, "a", ["name"])
    assert len(rows) == 2


def test_text_handles_missing_and_none_fields():
    rows = [{"name": None}, {}, {"name": "Real"}]
    assert filter_by_text(rows, "real", ["name"]) == [{"name": "Real"}]


# ---------------------------------------------------------------------------
# filter_phases
# ---------------------------------------------------------------------------

_PHASES = [
    {"name": "Fase Invierno", "is_active": True},
    {"name": "Fase Verano", "is_active": False},
    {"name": "Liga Primavera", "is_active": False},
]


def test_phases_estado_todas_no_filter():
    assert filter_phases(_PHASES, estado="Todas") == _PHASES


def test_phases_estado_activa():
    out = filter_phases(_PHASES, estado="Activa")
    assert [p["name"] for p in out] == ["Fase Invierno"]


def test_phases_estado_inactiva():
    out = filter_phases(_PHASES, estado="Inactiva")
    assert [p["name"] for p in out] == ["Fase Verano", "Liga Primavera"]


def test_phases_text_and_estado_combined():
    out = filter_phases(_PHASES, query="fase", estado="Inactiva")
    assert [p["name"] for p in out] == ["Fase Verano"]


# ---------------------------------------------------------------------------
# Torneos
# ---------------------------------------------------------------------------

def _t(name, divisions=None, matches=None):
    return {
        "name": name,
        "tournament_data": {
            "divisions": divisions or [],
            "matches": matches or [],
        },
    }


_TOURNEYS = [
    _t("Open Masculino", ["masculino:1a"], matches=[{"winner_id": "x"}]),
    _t("Torneo Mixto", ["mixto:3a"], matches=[]),
    _t("Multi", ["masculino:1a", "femenino:2a"], matches=[]),
]


def test_tournament_divisions_extracts_keys():
    assert tournament_divisions(_TOURNEYS[2]) == ["masculino:1a", "femenino:2a"]


def test_tournament_divisions_missing_data():
    assert tournament_divisions({"name": "x"}) == []


def test_all_division_keys_sorted_unique():
    assert all_division_keys(_TOURNEYS) == ["femenino:2a", "masculino:1a", "mixto:3a"]


def test_tournaments_text_filter():
    out = filter_tournaments(_TOURNEYS, query="mixto")
    assert [r["name"] for r in out] == ["Torneo Mixto"]


def test_tournaments_category_filter_matches_any():
    out = filter_tournaments(_TOURNEYS, categories=["masculino:1a"])
    assert {r["name"] for r in out} == {"Open Masculino", "Multi"}


def test_tournaments_category_filter_empty_is_noop():
    assert filter_tournaments(_TOURNEYS, categories=[]) == _TOURNEYS


def test_tournaments_status_filter_with_injected_fn():
    def status_of(row):
        return "En juego" if row["tournament_data"]["matches"] else "Configurado"

    out = filter_tournaments(_TOURNEYS, statuses=["En juego"], status_of=status_of)
    assert [r["name"] for r in out] == ["Open Masculino"]


def test_tournaments_status_ignored_without_status_fn():
    # statuses sin status_of => no filtra por estado
    out = filter_tournaments(_TOURNEYS, statuses=["En juego"], status_of=None)
    assert out == _TOURNEYS


def test_tournaments_combined_filters():
    out = filter_tournaments(_TOURNEYS, query="o", categories=["masculino:1a"])
    assert {r["name"] for r in out} == {"Open Masculino"}


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------

_CLUBS = [
    {"name": "Pádel Madrid", "slug": "padel-madrid"},
    {"name": "Club Barcelona", "slug": "club-bcn"},
]


def test_clubs_by_name():
    assert filter_clubs(_CLUBS, "madrid") == [_CLUBS[0]]


def test_clubs_by_slug():
    assert filter_clubs(_CLUBS, "bcn") == [_CLUBS[1]]


def test_clubs_empty_query():
    assert filter_clubs(_CLUBS, "") == _CLUBS


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

_USERS = [
    {"username": "admin_mad", "display_name": "Admin Madrid", "email": "a@mad.es",
     "role": "club_admin", "club_id": "c1"},
    {"username": "super", "display_name": "Super", "email": "s@v.es",
     "role": "superadmin", "club_id": None},
    {"username": "admin_bcn", "display_name": "Admin BCN", "email": "b@bcn.es",
     "role": "club_admin", "club_id": "c2"},
]


def test_users_text_on_email():
    out = filter_users(_USERS, query="bcn.es")
    assert [u["username"] for u in out] == ["admin_bcn"]


def test_users_role_filter():
    out = filter_users(_USERS, role="superadmin")
    assert [u["username"] for u in out] == ["super"]


def test_users_role_todos_noop():
    assert filter_users(_USERS, role="Todos") == _USERS


def test_users_club_filter_by_id():
    out = filter_users(_USERS, club_id="c2")
    assert [u["username"] for u in out] == ["admin_bcn"]


def test_users_club_filter_none_matches_superadmin():
    out = filter_users(_USERS, club_id=None)
    assert [u["username"] for u in out] == ["super"]


def test_users_club_all_is_noop():
    assert filter_users(_USERS, club_id=ALL) == _USERS


def test_users_combined_role_and_text():
    out = filter_users(_USERS, query="admin", role="club_admin", club_id="c1")
    assert [u["username"] for u in out] == ["admin_mad"]
