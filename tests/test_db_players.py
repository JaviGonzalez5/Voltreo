"""Tests de cuentas de jugador y directorio público (src/db_players.py)."""
from datetime import date

import pytest

import src.db_elo as db_elo
import src.db_players as db_players
from tests.test_db_elo import _FakeClient, _FakeDB


@pytest.fixture()
def fake_db(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(db_elo, "get_db", lambda: _FakeDB(client))
    monkeypatch.setattr(db_players, "get_db", lambda: _FakeDB(client))
    return client


class TestValidateSignup:
    def test_valid_data_no_errors(self):
        errs = db_players.validate_signup(
            "Ana", "García", "600123123", "ana@x.com", "12345678Z",
            "secret9", "secret9")
        assert errs == []

    def test_each_field_validated(self):
        errs = db_players.validate_signup("", "", "", "no-email", "123", "ab", "cd")
        joined = " ".join(errs)
        for frag in ("nombre", "apellido", "teléfono", "email", "DNI",
                     "contraseña", "no coinciden"):
            assert frag.lower() in joined.lower(), f"falta validación de {frag}"


class TestAccounts:
    def test_create_links_elo_identity(self, fake_db):
        acc = db_players.create_player_account(
            "club1", "Ana", "García", "600", "ana@x.com", "12345678Z", "secret9")
        assert acc["email"] == "ana@x.com"
        assert acc["player_id"]                      # vinculado a players
        players = fake_db.store["players"]
        assert any(p["id"] == acc["player_id"] and p["full_name"] == "Ana García"
                   for p in players)

    def test_duplicate_email_rejected(self, fake_db):
        db_players.create_player_account(
            "club1", "Ana", "García", "600", "ana@x.com", "12345678Z", "secret9")
        with pytest.raises(ValueError):
            db_players.create_player_account(
                "club1", "Otra", "Persona", "601", "ANA@x.com", "87654321X", "secret9")

    def test_login_ok_and_wrong_password(self, fake_db):
        db_players.create_player_account(
            "club1", "Ana", "García", "600", "ana@x.com", "12345678Z", "secret9")
        assert db_players.login_player("ana@x.com", "secret9") is not None
        assert db_players.login_player("ana@x.com", "mala") is None
        assert db_players.login_player("nadie@x.com", "secret9") is None

    def test_password_not_stored_in_plain(self, fake_db):
        db_players.create_player_account(
            "club1", "Ana", "García", "600", "ana@x.com", "12345678Z", "secret9")
        acc = fake_db.store["player_accounts"][0]
        assert "secret9" not in acc["password_hash"]
        assert acc["password_hash"].startswith("$2")   # bcrypt

    def test_elo_history_visible_after_club_records_match(self, fake_db):
        """El flujo clave: el jugador se registra; el club registra un partido
        con su nombre → el histórico aparece en SU identidad."""
        acc = db_players.create_player_account(
            "club1", "Ana", "García", "600", "ana@x.com", "12345678Z", "secret9")
        # El club registra un resultado donde juega "Ana García"
        ids = {}
        for n in ("Ana García", "Bea", "Carla", "Diana"):
            ids[n] = db_elo.get_or_create_player("club1", n)["id"]
        assert ids["Ana García"] == acc["player_id"]   # MISMA identidad
        db_elo.record_match_result(
            club_id="club1", context="tournament", source_id="m1",
            event_name="Open", pair_a_player_ids=(ids["Ana García"], ids["Bea"]),
            pair_a_names=("Ana García", "Bea"),
            pair_b_player_ids=(ids["Carla"], ids["Diana"]),
            pair_b_names=("Carla", "Diana"), winner_pair="A", score="6-1 6-1")
        hist = db_elo.get_player_history(acc["player_id"], "tournament")
        assert len(hist) == 1 and "Open" in hist[0]["tournament_name"]


class TestDirectory:
    def test_is_active_event(self):
        today = date(2026, 6, 10)
        assert db_players.is_active_event({"end_date": "2026-06-10"}, today)
        assert db_players.is_active_event({"end_date": "2026-07-01"}, today)
        assert not db_players.is_active_event({"end_date": "2026-06-09"}, today)
        assert not db_players.is_active_event({"end_date": ""}, today)

    def test_active_tournaments_with_club_names(self, fake_db, monkeypatch):
        fake_db.store["clubs"] = [{"id": "club1", "name": "Padelplus"}]
        fake_db.store["tournaments"] = [
            {"id": "t1", "club_id": "club1", "name": "Open Verano",
             "start_date": "2099-07-01", "end_date": "2099-07-10",
             "tournament_data": {"registration_open": True, "location": "Vigo"}},
            {"id": "t2", "club_id": "club1", "name": "Viejo",
             "start_date": "2020-01-01", "end_date": "2020-01-02",
             "tournament_data": {}},
        ]
        out = db_players.list_active_tournaments_all()
        assert len(out) == 1
        assert out[0]["name"] == "Open Verano"
        assert out[0]["club_name"] == "Padelplus"
        assert out[0]["registration_open"] is True

    def test_active_phases_only_is_active(self, fake_db):
        fake_db.store["clubs"] = [{"id": "club1", "name": "Padelplus"}]
        fake_db.store["ranking_phases"] = [
            {"id": "p1", "club_id": "club1", "name": "Fase 5",
             "start_date": "2099-01-01", "end_date": "2099-03-01", "is_active": True},
            {"id": "p2", "club_id": "club1", "name": "Fase vieja",
             "start_date": "2099-01-01", "end_date": "2099-03-01", "is_active": False},
        ]
        out = db_players.list_active_phases_all()
        assert [p["id"] for p in out] == ["p1"]
