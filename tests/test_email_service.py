"""
Tests para src/email_service.py
Cubre: generación de HTML, fallback sin SMTP, fallo de envío, destinatarios vacíos.
No requiere conexión SMTP real.
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_call(**kwargs):
    """Argumentos base para send_registration_confirmation."""
    defaults = dict(
        to_emails=["player@example.com"],
        tournament_name="Torneo Verano",
        pair_name="García / López",
        category="1ª",
        player1_full="Ana García",
        player2_full="Luis López",
    )
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

class TestHtmlEmail:

    def _html(self, **kwargs):
        from src.email_service import _html_email
        defaults = dict(
            tournament_name="Torneo Verano",
            pair_name="García / López",
            category="1ª",
            player1_full="Ana García",
            player2_full="Luis López",
        )
        defaults.update(kwargs)
        return _html_email(**defaults)

    def test_html_escapes_xss_in_tournament_name(self):
        html = self._html(tournament_name='<script>alert(1)</script>')
        assert '<script>' not in html

    def test_html_escapes_xss_in_pair_name(self):
        html = self._html(pair_name='<img src=x onerror=alert(1)>')
        assert '<img' not in html

    def test_html_contains_pair_name(self):
        html = self._html(pair_name="Martín / Ruiz")
        assert "Martín / Ruiz" in html

    def test_html_contains_player_names(self):
        html = self._html(player1_full="Carlos Martín", player2_full="Pedro Ruiz")
        assert "Carlos Martín" in html
        assert "Pedro Ruiz" in html

    def test_html_category_row_absent_when_empty(self):
        html = self._html(category="")
        # La fila de categoría no debe aparecer si está vacía
        assert "Categoría" not in html

    def test_html_is_valid_doctype(self):
        html = self._html()
        assert html.strip().startswith("<!DOCTYPE html>")


# ---------------------------------------------------------------------------
# send_registration_confirmation
# ---------------------------------------------------------------------------

class TestSendRegistrationConfirmation:

    def test_returns_false_when_smtp_not_configured(self):
        """Sin secrets SMTP configurados devuelve (False, str) sin lanzar."""
        with patch("src.email_service._get_smtp_config", return_value=None):
            from src.email_service import send_registration_confirmation
            ok, msg = send_registration_confirmation(**_make_call())
        assert ok is False
        assert isinstance(msg, str)

    def test_returns_false_on_smtp_connection_error(self):
        """Fallo de conexión SMTP devuelve (False, str) sin propagar excepción."""
        cfg = {"host": "smtp.example.com", "port": 587,
               "user": "u", "password": "p", "from": "u@example.com"}
        with patch("src.email_service._get_smtp_config", return_value=cfg), \
             patch("smtplib.SMTP", side_effect=OSError("Connection refused")):
            from src.email_service import send_registration_confirmation
            ok, msg = send_registration_confirmation(**_make_call())
        assert ok is False
        assert "Error" in msg or "error" in msg.lower()

    def test_returns_false_for_empty_recipient_list(self):
        """Lista de destinatarios vacía devuelve (False, str) sin intentar SMTP."""
        with patch("src.email_service._get_smtp_config",
                   return_value={"host": "h", "port": 587, "user": "u",
                                 "password": "p", "from": "u@h"}):
            from src.email_service import send_registration_confirmation
            ok, msg = send_registration_confirmation(**_make_call(to_emails=[]))
        assert ok is False
        assert isinstance(msg, str)

    def test_returns_true_on_successful_send(self):
        """Mock SMTP completo: devuelve (True, str) con destinatario en el mensaje."""
        cfg = {"host": "smtp.example.com", "port": 587,
               "user": "u", "password": "p", "from": "u@example.com"}
        mock_server = MagicMock()
        mock_smtp_cls = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_server
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.email_service._get_smtp_config", return_value=cfg), \
             patch("smtplib.SMTP", mock_smtp_cls):
            from src.email_service import send_registration_confirmation
            ok, msg = send_registration_confirmation(**_make_call())
        assert ok is True
        assert "player@example.com" in msg
