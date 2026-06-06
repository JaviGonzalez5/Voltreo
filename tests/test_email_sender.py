"""
Tests para src/email_sender.py (sistema unificado vía Resend).
Cubre: generación de HTML de inscripción, fallback sin Resend, filtrado de
destinatarios inválidos, envío correcto. No requiere conexión real.
"""
import pytest
from unittest.mock import patch


def _make_call(**kwargs):
    """Argumentos base para notify_registration_received."""
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
# HTML generation (_registration_html)
# ---------------------------------------------------------------------------

class TestRegistrationHtml:

    def _html(self, **kwargs):
        from src.email_sender import _registration_html
        defaults = dict(
            tournament_name="Torneo Verano",
            pair_name="García / López",
            category="1ª",
            player1_full="Ana García",
            player2_full="Luis López",
        )
        defaults.update(kwargs)
        return _registration_html(**defaults)

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
        assert "Categoría" not in html

    def test_html_is_valid_doctype(self):
        html = self._html()
        assert html.strip().startswith("<!DOCTYPE html>")


# ---------------------------------------------------------------------------
# notify_registration_received
# ---------------------------------------------------------------------------

class TestNotifyRegistrationReceived:

    def test_returns_false_when_resend_not_configured(self):
        """Sin RESEND_API_KEY devuelve False sin lanzar y sin llamar a _send."""
        with patch("src.email_sender.is_email_configured", return_value=False), \
             patch("src.email_sender._send") as mock_send:
            from src.email_sender import notify_registration_received
            result = notify_registration_received(**_make_call())
        assert result is False
        mock_send.assert_not_called()

    def test_returns_false_for_empty_recipient_list(self):
        """Lista vacía: False, sin intentar enviar."""
        with patch("src.email_sender.is_email_configured", return_value=True), \
             patch("src.email_sender._send") as mock_send:
            from src.email_sender import notify_registration_received
            result = notify_registration_received(**_make_call(to_emails=[]))
        assert result is False
        mock_send.assert_not_called()

    def test_filters_invalid_emails(self):
        """None, vacíos y sin '@' se descartan antes de enviar."""
        captured = {}

        def fake_send(to, subject, html):
            captured["to"] = to
            return True

        with patch("src.email_sender.is_email_configured", return_value=True), \
             patch("src.email_sender._send", side_effect=fake_send):
            from src.email_sender import notify_registration_received
            result = notify_registration_received(
                **_make_call(to_emails=["ok@x.com", "", None, "noarroba", "ok2@x.com"])
            )
        assert result is True
        assert captured["to"] == ["ok@x.com", "ok2@x.com"]

    def test_returns_false_when_all_emails_invalid(self):
        """Si tras filtrar no queda ninguno, False sin enviar."""
        with patch("src.email_sender.is_email_configured", return_value=True), \
             patch("src.email_sender._send") as mock_send:
            from src.email_sender import notify_registration_received
            result = notify_registration_received(
                **_make_call(to_emails=["", None, "noarroba"])
            )
        assert result is False
        mock_send.assert_not_called()

    def test_returns_true_on_successful_send(self):
        """Envío correcto: True, subject con nombre del torneo, HTML válido."""
        captured = {}

        def fake_send(to, subject, html):
            captured["subject"] = subject
            captured["html"] = html
            return True

        with patch("src.email_sender.is_email_configured", return_value=True), \
             patch("src.email_sender._send", side_effect=fake_send):
            from src.email_sender import notify_registration_received
            result = notify_registration_received(**_make_call())
        assert result is True
        assert "Torneo Verano" in captured["subject"]
        assert "<!DOCTYPE html>" in captured["html"]
