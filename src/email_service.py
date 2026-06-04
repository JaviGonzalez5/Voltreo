"""
Servicio de envío de correos electrónicos para Voltreo.

Configuración en .streamlit/secrets.toml:
    [email]
    smtp_host     = "smtp.gmail.com"
    smtp_port     = 587
    smtp_user     = "tu@gmail.com"
    smtp_password = "contraseña_de_aplicacion"
    smtp_from     = "Voltreo <tu@gmail.com>"

Para Gmail: usa una «contraseña de aplicación» (no la contraseña normal).
Guía: https://support.google.com/accounts/answer/185833
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Optional

from .branding import BRAND_NAME, BRAND_GRADIENT


def _get_smtp_config() -> Optional[dict]:
    """Lee la configuración SMTP de los secrets de Streamlit. Devuelve None si no está."""
    try:
        import streamlit as st
        cfg = st.secrets.get("email", {})
        if not cfg.get("smtp_host") or not cfg.get("smtp_user") or not cfg.get("smtp_password"):
            return None
        return {
            "host":     cfg.get("smtp_host", "smtp.gmail.com"),
            "port":     int(cfg.get("smtp_port", 587)),
            "user":     cfg["smtp_user"],
            "password": cfg["smtp_password"],
            "from":     cfg.get("smtp_from", cfg["smtp_user"]),
        }
    except Exception:
        return None


def _html_email(
    tournament_name: str,
    pair_name: str,
    category: str,
    player1_full: str,
    player2_full: str,
    extra_note: str = "",
) -> str:
    """Genera el HTML del correo de confirmación de inscripción."""
    cat_row = (
        f'<tr><td style="padding:6px 0;color:#6b7280;font-size:.9rem">Categoría</td>'
        f'<td style="padding:6px 0;font-weight:600;color:#111827">{escape(category)}</td></tr>'
        if category else ""
    )
    note_row = (
        f'<p style="margin:16px 0 0;padding:12px 16px;background:#f0fdf4;'
        f'border-left:4px solid #00c853;border-radius:4px;font-size:.88rem;color:#065f46">'
        f'{escape(extra_note)}</p>'
        if extra_note else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:32px 16px">
    <tr><td align="center">
      <table width="100%" style="max-width:560px;background:#fff;border-radius:16px;
             overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">

        <!-- Cabecera con gradiente -->
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

        <!-- Cuerpo -->
        <tr><td style="padding:28px 32px">
          <h2 style="margin:0 0 6px;color:#111827;font-size:1.15rem;font-weight:800">
            ✅ Inscripción recibida</h2>
          <p style="margin:0 0 20px;color:#6b7280;font-size:.9rem">
            Tu solicitud ha sido enviada correctamente. El club la revisará y te confirmará pronto.</p>

          <!-- Datos del torneo -->
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
                  <td style="padding:6px 0"><span style="background:#fef3c7;color:#92400e;
                    border-radius:20px;padding:2px 10px;font-size:.82rem;font-weight:700">
                    ⏳ Pendiente de confirmación</span></td></tr>
            </table>
          </div>

          {note_row}

          <p style="margin:20px 0 0;color:#9ca3af;font-size:.82rem">
            Cuando el club confirme tu plaza recibirás otro correo. Si tienes dudas,
            contacta directamente con los organizadores.</p>
        </td></tr>

        <!-- Footer -->
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


def send_registration_confirmation(
    to_emails: list[str],
    tournament_name: str,
    pair_name: str,
    category: str,
    player1_full: str,
    player2_full: str,
) -> tuple[bool, str]:
    """
    Envía el correo de confirmación de inscripción a los emails indicados.

    Returns:
        (success: bool, message: str)
    """
    cfg = _get_smtp_config()
    if not cfg:
        return False, "Email no configurado (falta [email] en secrets.toml)"

    recipients = [e.strip() for e in to_emails if e and e.strip()]
    if not recipients:
        return False, "No hay dirección de email a la que enviar"

    html_body = _html_email(
        tournament_name=tournament_name,
        pair_name=pair_name,
        category=category,
        player1_full=player1_full,
        player2_full=player2_full,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✅ Inscripción recibida — {tournament_name}"
    msg["From"]    = cfg["from"]
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(
        f"Inscripción recibida en {tournament_name}.\n"
        f"Pareja: {pair_name}\n"
        f"Jugador 1: {player1_full}\nJugador 2: {player2_full}\n"
        f"Estado: Pendiente de confirmación por el club.",
        "plain", "utf-8",
    ))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from"], recipients, msg.as_string())
        return True, f"Correo enviado a {', '.join(recipients)}"
    except Exception as exc:
        return False, f"Error al enviar email: {exc}"
