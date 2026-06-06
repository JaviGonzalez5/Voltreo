"""
Tests de smoke: importabilidad de módulos clave y regresiones estructurales de app.py.
No arrancan Streamlit ni requieren BD.
"""
import py_compile
from pathlib import Path

ROOT = Path(__file__).parent.parent


class TestCompilation:

    def test_app_py_compiles(self):
        py_compile.compile(str(ROOT / "app.py"), doraise=True)

    def test_auth_compiles(self):
        py_compile.compile(str(ROOT / "src" / "auth.py"), doraise=True)

    def test_email_sender_compiles(self):
        py_compile.compile(str(ROOT / "src" / "email_sender.py"), doraise=True)


class TestAuthModule:

    def test_auth_imports(self):
        import src.auth  # noqa: F401

    def test_rate_limit_store_exists(self):
        from src.auth import _rate_limit_store, _rate_limit_lock
        assert isinstance(_rate_limit_store, dict)

    def test_check_rate_limit_signature(self):
        from src.auth import check_rate_limit
        # Firma nueva: acepta username como argumento
        blocked, secs = check_rate_limit("anyuser")
        assert isinstance(blocked, bool)
        assert isinstance(secs, int)

    def test_old_session_state_keys_removed(self):
        """_login_attempts_key y _login_lockout_key fueron eliminadas en el refactor."""
        import src.auth as auth_mod
        assert not hasattr(auth_mod, "_login_attempts_key")
        assert not hasattr(auth_mod, "_login_lockout_key")


class TestEmailSenderModule:

    def test_email_sender_imports(self):
        import src.email_sender  # noqa: F401

    def test_notify_function_exists(self):
        from src.email_sender import notify_registration_received
        assert callable(notify_registration_received)

    def test_html_function_exists(self):
        from src.email_sender import _registration_html
        assert callable(_registration_html)


class TestAppPyStructure:

    def _src(self):
        return (ROOT / "app.py").read_text(encoding="utf-8")

    def test_health_check_before_set_page_config(self):
        """Regresión: el health-check debe resolverse ANTES del st.set_page_config principal."""
        src = self._src()
        health_pos = src.index("_early_health")
        config_pos = src.index('st.set_page_config(\n    page_title=')
        assert health_pos < config_pos, (
            "El bloque _early_health debe aparecer antes de st.set_page_config "
            "para evitar StreamlitAPIException en el endpoint ?health=1"
        )

    def test_logging_imported(self):
        """import logging debe estar presente para las excepciones silenciadas."""
        src = self._src()
        assert "import logging" in src

    def test_no_duplicate_set_page_config_outside_health(self):
        """Solo debe haber UN st.set_page_config fuera del bloque health-check."""
        src = self._src()
        # El bloque health-check tiene su propio set_page_config; el resto del
        # archivo debe tener exactamente uno más (el principal).
        count = src.count("st.set_page_config(")
        assert count == 2, (
            f"Se esperaban 2 llamadas a st.set_page_config (health + principal), "
            f"encontradas: {count}"
        )
