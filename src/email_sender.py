"""
Envío de emails transaccionales vía Resend.

Configuración (variable de entorno o Streamlit secrets):
    RESEND_API_KEY=re_xxxxxxxxxxxx
    EMAIL_FROM=noreply@tuclub.com   (opcional, default: Voltreo <noreply@voltreo.app>)

Si RESEND_API_KEY no está configurado, todas las funciones devuelven False/0
silenciosamente para no bloquear la app.
"""

import os
import logging
from html import escape
from typing import Optional

from .branding import BRAND_NAME

log = logging.getLogger(__name__)

_RESEND_KEY: Optional[str] = None
_FROM_ADDR: str = "Voltreo <noreply@voltreo.app>"


def _get_key() -> Optional[str]:
    global _RESEND_KEY
    if _RESEND_KEY is None:
        _RESEND_KEY = os.getenv("RESEND_API_KEY", "")
    return _RESEND_KEY or None


def is_email_configured() -> bool:
    return bool(_get_key())


def _send(to: list[str], subject: str, html: str) -> bool:
    """Envía un email vía Resend. Devuelve True si se envió correctamente."""
    key = _get_key()
    if not key:
        return False
    try:
        import resend  # type: ignore
        resend.api_key = key
        from_addr = os.getenv("EMAIL_FROM", _FROM_ADDR)
        resend.Emails.send({"from": from_addr, "to": to, "subject": subject, "html": html})
        return True
    except Exception as e:
        log.warning("Email no enviado: %s", e)
        return False


def _result_html(
    pair_name: str,
    rival_name: str,
    score: str,
    won: bool,
    phase_name: str,
    club_name: str,
    public_url: Optional[str] = None,
) -> str:
    color = "#00843d" if won else "#c62828"
    result_text = "Victoria" if won else "Derrota"
    link_html = (
        f'<p style="margin-top:24px"><a href="{public_url}" '
        f'style="background:#00c853;color:#fff;padding:10px 20px;border-radius:8px;'
        f'text-decoration:none;font-weight:700">Ver clasificación actualizada</a></p>'
        if public_url else ""
    )
    return f"""
<div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;background:#f9f9f9;
            border-radius:12px;padding:28px;border:1px solid #e0e0e0">
  <h2 style="color:#1a1a2e;margin-top:0">🎾 Resultado registrado — {phase_name}</h2>
  <p style="font-size:16px;color:#333">
    <strong>{pair_name}</strong> vs <strong>{rival_name}</strong>
  </p>
  <p style="font-size:22px;font-weight:700;color:{color}">{result_text} · {score or "—"}</p>
  {link_html}
  <p style="font-size:12px;color:#999;margin-top:24px">
    Enviado por {club_name} a través de Voltreo. No respondas a este correo.
  </p>
</div>
"""


def notify_result(
    pair_1_emails: list[str],
    pair_2_emails: list[str],
    pair_1_name: str,
    pair_2_name: str,
    winner_name: Optional[str],
    score: str,
    phase_name: str,
    club_name: str,
    public_url: Optional[str] = None,
) -> int:
    """
    Envía notificación de resultado a ambas parejas.
    Devuelve el número de emails enviados (0 si email no configurado).
    """
    if not is_email_configured():
        return 0

    sent = 0
    for emails, name, rival, won in [
        (pair_1_emails, pair_1_name, pair_2_name, winner_name == pair_1_name),
        (pair_2_emails, pair_2_name, pair_1_name, winner_name == pair_2_name),
    ]:
        reachable = [e for e in emails if e and "@" in e]
        if not reachable:
            continue
        html = _result_html(name, rival, score, won, phase_name, club_name, public_url)
        subject = f"🎾 Resultado: {pair_1_name} vs {pair_2_name} — {phase_name}"
        if _send(reachable, subject, html):
            sent += len(reachable)
    return sent


def notify_bracket_published(
    participant_emails: list[str],
    tournament_name: str,
    club_name: str,
    public_url: Optional[str] = None,
) -> int:
    """Notifica a todos los participantes que el cuadro del torneo ha sido publicado."""
    if not is_email_configured():
        return 0
    reachable = [e for e in participant_emails if e and "@" in e]
    if not reachable:
        return 0

    link_html = (
        f'<p style="margin-top:24px"><a href="{public_url}" '
        f'style="background:#00c853;color:#fff;padding:10px 20px;border-radius:8px;'
        f'text-decoration:none;font-weight:700">Ver cuadro del torneo</a></p>'
        if public_url else ""
    )
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:500px;margin:auto;background:#f9f9f9;
            border-radius:12px;padding:28px;border:1px solid #e0e0e0">
  <h2 style="color:#1a1a2e;margin-top:0">🏆 Cuadro publicado — {tournament_name}</h2>
  <p style="font-size:15px;color:#333">
    El cuadro del torneo <strong>{tournament_name}</strong> ha sido publicado.
    Consulta tu posición y los partidos programados en el enlace de abajo.
  </p>
  {link_html}
  <p style="font-size:12px;color:#999;margin-top:24px">
    Enviado por {club_name} a través de Voltreo.
  </p>
</div>
"""
    subject = f"🏆 Cuadro publicado: {tournament_name}"
    sent = 0
    for email in reachable:
        if _send([email], subject, html):
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# Confirmación de inscripción en torneo
# ---------------------------------------------------------------------------

def _registration_html(
    tournament_name: str,
    pair_name: str,
    category: str,
    player1_full: str,
    player2_full: str,
) -> str:
    """HTML del correo de confirmación de inscripción en torneo."""
    cat_row = (
        f'<tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Categoría</td>'
        f'<td style="padding:6px 0;font-weight:600;color:#111827">{escape(category)}</td></tr>'
        if category else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:32px 16px">
    <tr><td align="center">
      <table width="100%" style="max-width:560px;background:#fff;border-radius:16px;
             overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

        <tr><td style="background:linear-gradient(135deg,#00c853,#00897b);
                padding:28px 32px;text-align:center">
          <div style="display:inline-block;width:44px;height:44px;border-radius:12px;
               background:rgba(255,255,255,.25);text-align:center;line-height:44px;
               font-size:1.4rem;font-weight:900;color:#fff;margin-bottom:10px">V</div>
          <h1 style="margin:0;color:#fff;font-size:1.35rem;font-weight:800;
                     letter-spacing:-.02em">{escape(BRAND_NAME)}</h1>
          <p style="margin:4px 0 0;color:rgba(255,255,255,.85);font-size:.85rem">
            Gestión de torneos deportivos</p>
        </td></tr>

        <tr><td style="padding:28px 32px">
          <h2 style="margin:0 0 6px;color:#111827;font-size:1.15rem;font-weight:800">
            ✅ Inscripción recibida</h2>
          <p style="margin:0 0 20px;color:#6b7280;font-size:.9rem">
            Tu solicitud ha sido enviada correctamente.
            El club la revisará y te confirmará pronto.</p>

          <div style="background:#f9fafb;border:1px solid #e9ecef;border-radius:12px;
                      padding:16px 20px;margin-bottom:20px">
            <p style="margin:0 0 12px;font-size:.72rem;font-weight:800;letter-spacing:.1em;
                      text-transform:uppercase;color:#9ca3af">Torneo</p>
            <p style="margin:0 0 10px;font-size:1.05rem;font-weight:800;color:#111827">
              {escape(tournament_name)}</p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Pareja</td>
                  <td style="padding:6px 0;font-weight:700;color:#111827">{escape(pair_name)}</td></tr>
              {cat_row}
              <tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Jugador 1</td>
                  <td style="padding:6px 0;color:#374151">{escape(player1_full)}</td></tr>
              <tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Jugador 2</td>
                  <td style="padding:6px 0;color:#374151">{escape(player2_full)}</td></tr>
              <tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Estado</td>
                  <td style="padding:6px 0">
                    <span style="background:#fef3c7;color:#92400e;border-radius:20px;
                          padding:2px 10px;font-size:.82rem;font-weight:700">
                      ⏳ Pendiente de confirmación</span></td></tr>
            </table>
          </div>

          <p style="margin:20px 0 0;color:#9ca3af;font-size:.82rem">
            Cuando el club confirme tu plaza recibirás otro correo.
            Si tienes dudas, contacta directamente con los organizadores.</p>
        </td></tr>

        <tr><td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e9ecef;
                text-align:center">
          <p style="margin:0;color:#9ca3af;font-size:.78rem">
            Correo generado automáticamente por
            <strong style="color:#00897b">{escape(BRAND_NAME)}</strong>.
            Por favor no respondas a este mensaje.</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def notify_registration_received(
    to_emails: list[str],
    tournament_name: str,
    pair_name: str,
    category: str,
    player1_full: str,
    player2_full: str,
) -> bool:
    """
    Envía confirmación de inscripción en torneo a los emails indicados.

    Filtra entradas vacías o sin '@' antes de enviar.
    Devuelve True si se envió al menos un email, False en cualquier otro caso
    (Resend no configurado, todos los emails inválidos, error de red…).
    La inscripción debe completarse aunque esta función devuelva False.
    """
    if not is_email_configured():
        return False

    recipients = [e.strip() for e in to_emails if e and e.strip() and "@" in e]
    if not recipients:
        return False

    html = _registration_html(
        tournament_name=tournament_name,
        pair_name=pair_name,
        category=category,
        player1_full=player1_full,
        player2_full=player2_full,
    )
    subject = f"✅ Inscripción recibida — {tournament_name}"
    return _send(recipients, subject, html)
