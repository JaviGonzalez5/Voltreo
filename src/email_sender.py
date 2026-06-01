"""
Envío de emails transaccionales vía Resend.

Configuración en .env:
    RESEND_API_KEY=re_xxxxxxxxxxxx
    EMAIL_FROM=noreply@tuclub.com        (opcional, default: Voltreo <noreply@voltreo.app>)

Si RESEND_API_KEY no está configurado, todas las funciones devuelven False silenciosamente
para no bloquear la app cuando el email no está configurado.
"""

import os
import logging
from typing import Optional

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
