"""
Tests de seguridad para src/auth.py
Cubre: rate limiting, validación de contraseña, aislamiento de sesión.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_session(monkeypatch):
    """Limpia el session_state de Streamlit antes de cada test."""
    session = {}
    import streamlit as st
    monkeypatch.setattr(st, "session_state", session)
    yield session


# ---------------------------------------------------------------------------
# validate_password_strength
# ---------------------------------------------------------------------------

class TestPasswordStrength:

    def test_strong_password_no_errors(self):
        from src.auth import validate_password_strength
        assert validate_password_strength("Padel2026!") == []

    def test_too_short(self):
        from src.auth import validate_password_strength
        errors = validate_password_strength("Ab1")
        assert any("8" in e for e in errors)

    def test_no_uppercase(self):
        from src.auth import validate_password_strength
        errors = validate_password_strength("padel2026")
        assert any("mayúscula" in e.lower() for e in errors)

    def test_no_digit(self):
        from src.auth import validate_password_strength
        errors = validate_password_strength("PadelPlus!")
        assert any("número" in e.lower() for e in errors)

    def test_multiple_issues(self):
        from src.auth import validate_password_strength
        errors = validate_password_strength("abc")
        assert len(errors) >= 2  # corto + sin mayúscula + sin número

    def test_exactly_8_chars_with_upper_and_digit(self):
        from src.auth import validate_password_strength
        assert validate_password_strength("Padel001") == []


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:

    def test_no_block_on_first_attempts(self, clean_session):
        from src.auth import check_rate_limit
        blocked, secs = check_rate_limit()
        assert not blocked
        assert secs == 0

    def test_block_after_max_attempts(self, clean_session):
        from src.auth import _record_failed_attempt, check_rate_limit, _MAX_ATTEMPTS
        for _ in range(_MAX_ATTEMPTS):
            _record_failed_attempt()
        blocked, secs = check_rate_limit()
        assert blocked
        assert secs > 0

    def test_lockout_seconds_approx_300(self, clean_session):
        from src.auth import _record_failed_attempt, check_rate_limit, _MAX_ATTEMPTS, _LOCKOUT_SECS
        for _ in range(_MAX_ATTEMPTS):
            _record_failed_attempt()
        _, secs = check_rate_limit()
        assert abs(secs - _LOCKOUT_SECS) < 5  # ±5s tolerancia

    def test_counter_resets_after_lockout(self, clean_session):
        """El contador de intentos se resetea al aplicar el bloqueo."""
        from src.auth import _record_failed_attempt, _login_attempts_key, _MAX_ATTEMPTS
        for _ in range(_MAX_ATTEMPTS):
            _record_failed_attempt()
        assert clean_session.get(_login_attempts_key(), 0) == 0

    def test_login_raises_when_blocked(self, clean_session):
        from src.auth import _record_failed_attempt, login, _MAX_ATTEMPTS
        for _ in range(_MAX_ATTEMPTS):
            _record_failed_attempt()
        db = MagicMock()
        with pytest.raises(RuntimeError, match="Demasiados intentos"):
            login(db, "user", "pass")

    def test_failed_login_increments_counter(self, clean_session):
        from src.auth import login, _login_attempts_key
        db = MagicMock()
        db.get_user_by_username.return_value = None  # usuario no existe
        login(db, "nonexistent", "pass")
        assert clean_session.get(_login_attempts_key(), 0) == 1

    def test_successful_login_clears_counter(self, clean_session):
        from src.auth import login, _login_attempts_key, _record_failed_attempt
        import bcrypt
        hashed = bcrypt.hashpw(b"Correct01", bcrypt.gensalt()).decode()
        db = MagicMock()
        db.get_user_by_username.return_value = {
            "id": "u1", "username": "admin", "password_hash": hashed,
            "role": "club_admin", "club_id": "club1",
            "display_name": "Admin", "is_active": True,
        }
        # Simular 2 intentos fallidos previos
        _record_failed_attempt()
        _record_failed_attempt()
        assert clean_session.get(_login_attempts_key(), 0) == 2
        login(db, "admin", "Correct01")
        assert clean_session.get(_login_attempts_key(), 0) == 0


# ---------------------------------------------------------------------------
# Login: comportamiento correcto
# ---------------------------------------------------------------------------

class TestLogin:

    def _make_db(self, password: str = "Padel2026") -> MagicMock:
        import bcrypt
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db = MagicMock()
        db.get_user_by_username.return_value = {
            "id": "u1", "username": "admin", "password_hash": hashed,
            "role": "club_admin", "club_id": "club1",
            "display_name": "Admin", "is_active": True,
        }
        return db

    def test_correct_credentials_return_user(self, clean_session):
        from src.auth import login
        db = self._make_db()
        user = login(db, "admin", "Padel2026")
        assert user is not None
        assert user["username"] == "admin"

    def test_wrong_password_returns_none(self, clean_session):
        from src.auth import login
        db = self._make_db()
        user = login(db, "admin", "WrongPass1")
        assert user is None

    def test_nonexistent_user_returns_none(self, clean_session):
        from src.auth import login
        db = MagicMock()
        db.get_user_by_username.return_value = None
        user = login(db, "nobody", "Pass1234")
        assert user is None

    def test_inactive_user_returns_none(self, clean_session):
        from src.auth import login
        import bcrypt
        hashed = bcrypt.hashpw(b"Padel2026", bcrypt.gensalt()).decode()
        db = MagicMock()
        db.get_user_by_username.return_value = {
            "id": "u1", "username": "disabled", "password_hash": hashed,
            "role": "club_admin", "club_id": "c1",
            "display_name": "D", "is_active": False,
        }
        user = login(db, "disabled", "Padel2026")
        assert user is None

    def test_username_normalized_to_lowercase(self, clean_session):
        from src.auth import login
        db = self._make_db()
        login(db, "ADMIN", "Padel2026")
        db.get_user_by_username.assert_called_once_with("admin")


# ---------------------------------------------------------------------------
# Multi-tenant isolation (unit level)
# ---------------------------------------------------------------------------

class TestMultiTenantIsolation:

    def test_current_club_id_returns_own_club_for_club_admin(self, clean_session):
        from src.auth import set_session_user, current_club_id
        set_session_user({"id":"u1","username":"a","display_name":"A",
                          "role":"club_admin","club_id":"clubA","is_active":True})
        assert current_club_id() == "clubA"

    def test_current_club_id_returns_selected_for_superadmin(self, clean_session):
        from src.auth import set_session_user, current_club_id
        set_session_user({"id":"su","username":"sa","display_name":"SA",
                          "role":"superadmin","club_id":None,"is_active":True})
        clean_session["superadmin_selected_club_id"] = "clubB"
        assert current_club_id() == "clubB"

    def test_current_club_id_returns_none_when_not_authenticated(self, clean_session):
        from src.auth import current_club_id
        assert current_club_id() is None

    def test_is_superadmin_false_for_club_admin(self, clean_session):
        from src.auth import set_session_user, is_superadmin
        set_session_user({"id":"u1","username":"a","display_name":"A",
                          "role":"club_admin","club_id":"c1","is_active":True})
        assert not is_superadmin()

    def test_is_superadmin_true_for_superadmin(self, clean_session):
        from src.auth import set_session_user, is_superadmin
        set_session_user({"id":"su","username":"sa","display_name":"SA",
                          "role":"superadmin","club_id":None,"is_active":True})
        assert is_superadmin()


# ---------------------------------------------------------------------------
# Aislamiento por club: un club_admin solo ve/gestiona su propio club
# ---------------------------------------------------------------------------

class TestClubIsolation:

    def _set_user(self, session, role, club_id):
        from src.auth import _AUTH_KEY
        session[_AUTH_KEY] = {
            "user_id": "u1", "username": "x", "display_name": "X",
            "role": role, "club_id": club_id, "club_name": "Mi Club",
        }

    def test_club_admin_current_club_is_own(self, clean_session):
        from src.auth import current_club_id
        self._set_user(clean_session, "club_admin", "clubA")
        assert current_club_id() == "clubA"

    def test_club_admin_cannot_override_club_via_superadmin_selector(self, clean_session):
        """Aunque exista superadmin_selected_club_id en sesión, el club_admin
        sigue atado a SU club — no puede ver otro club manipulando estado."""
        from src.auth import current_club_id
        self._set_user(clean_session, "club_admin", "clubA")
        clean_session["superadmin_selected_club_id"] = "clubB"  # intento de manipulación
        assert current_club_id() == "clubA"  # ignora el selector de superadmin

    def test_club_admin_is_not_superadmin(self, clean_session):
        from src.auth import is_superadmin
        self._set_user(clean_session, "club_admin", "clubA")
        assert is_superadmin() is False

    def test_superadmin_uses_selected_club(self, clean_session):
        from src.auth import current_club_id, is_superadmin
        self._set_user(clean_session, "superadmin", None)
        clean_session["superadmin_selected_club_id"] = "clubB"
        assert is_superadmin() is True
        assert current_club_id() == "clubB"

    def test_club_admin_name_is_own(self, clean_session):
        from src.auth import current_club_name
        self._set_user(clean_session, "club_admin", "clubA")
        assert current_club_name() == "Mi Club"
