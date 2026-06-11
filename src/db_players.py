"""
Cuentas de JUGADOR (autoservicio) — separadas de los usuarios admin.

Un jugador se registra con sus datos (nombre, apellido, teléfono, email, DNI)
y elige su club. Su cuenta se vincula a la identidad ELO (tabla players) por
nombre normalizado: cuando el club registra resultados con ese nombre, el
histórico y el ELO le aparecen automáticamente en su perfil.

Seguridad:
  · password con bcrypt.
  · El DNI se guarda pero NUNCA se muestra en el portal (solo identificación
    interna del club).
  · Tabla separada de `users` (admins): un jugador jamás toca el panel admin.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

import bcrypt

from .db import get_db
from .db_elo import get_or_create_player, _normalize_name_key

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def validate_signup(
    name: str, surname: str, phone: str, email: str, dni: str,
    password: str, password2: str,
) -> list[str]:
    """Validación del formulario de registro. Lista de errores legibles."""
    errors: list[str] = []
    if not str(name).strip():
        errors.append("El nombre es obligatorio.")
    if not str(surname).strip():
        errors.append("El primer apellido es obligatorio.")
    if not str(phone).strip():
        errors.append("El teléfono es obligatorio.")
    if not _EMAIL_RE.match(str(email).strip().lower()):
        errors.append("El email no es válido.")
    if len(str(dni).strip()) < 8:
        errors.append("El DNI/NIE no es válido.")
    if len(password or "") < 6:
        errors.append("La contraseña debe tener al menos 6 caracteres.")
    if password != password2:
        errors.append("Las contraseñas no coinciden.")
    return errors


def get_account_by_email(email: str) -> Optional[dict]:
    db = get_db()
    resp = (db._c.table("player_accounts").select("*")
            .eq("email", str(email).strip().lower()).execute())
    return resp.data[0] if resp.data else None


def create_player_account(
    club_id: str, name: str, surname: str, phone: str,
    email: str, dni: str, password: str,
) -> dict:
    """
    Crea la cuenta y la vincula (o crea) su identidad ELO en `players`.
    Lanza ValueError si el email ya está registrado.
    """
    email_n = str(email).strip().lower()
    if get_account_by_email(email_n):
        raise ValueError("Ya existe una cuenta con ese email.")

    full_name = f"{str(name).strip()} {str(surname).strip()}".strip()
    player = None
    try:
        player = get_or_create_player(club_id, full_name, email=email_n,
                                      phone=str(phone).strip())
    except Exception:
        log.exception("No se pudo vincular identidad ELO en el registro")

    db = get_db()
    payload = {
        "club_id": club_id,
        "email": email_n,
        "password_hash": _hash_password(password),
        "full_name": full_name,
        "name": str(name).strip(),
        "surname": str(surname).strip(),
        "phone": str(phone).strip(),
        "dni": str(dni).strip().upper(),
        "player_id": player["id"] if player else None,
    }
    resp = db._c.table("player_accounts").insert(payload).execute()
    if resp.data:
        return resp.data[0]
    return get_account_by_email(email_n) or payload


def login_player(email: str, password: str) -> Optional[dict]:
    """Devuelve la cuenta si email+password son correctos; None si no."""
    acc = get_account_by_email(email)
    if not acc:
        return None
    if not _verify_password(password, acc.get("password_hash", "")):
        return None
    return acc


def relink_player_identity(account: dict) -> Optional[dict]:
    """Re-vincula la cuenta a su fila de `players` (por nombre, en su club)."""
    try:
        player = get_or_create_player(
            account["club_id"], account.get("full_name", ""),
            email=account.get("email", ""), phone=account.get("phone", ""),
        )
        if player and account.get("player_id") != player["id"]:
            db = get_db()
            db._c.table("player_accounts").update(
                {"player_id": player["id"]}
            ).eq("id", account["id"]).execute()
            account["player_id"] = player["id"]
        return player
    except Exception:
        log.exception("relink_player_identity falló")
        return None


# ---------------------------------------------------------------------------
# Directorio público de competiciones activas (todos los clubs)
# ---------------------------------------------------------------------------

def is_active_event(row: dict, today: Optional[date] = None) -> bool:
    """Activo = aún no ha terminado (end_date >= hoy)."""
    today = today or date.today()
    end = str(row.get("end_date") or "")
    try:
        y, m, d = (int(x) for x in end.split("-")[:3])
        return date(y, m, d) >= today
    except Exception:
        return False


def list_active_tournaments_all() -> list[dict]:
    """Torneos activos de TODOS los clubs, con nombre de club.
    Devuelve dicts: id, name, club_name, start_date, end_date, registration_open."""
    db = get_db()
    resp = (db._c.table("tournaments")
            .select("id, club_id, name, start_date, end_date, tournament_data")
            .execute())
    rows = [r for r in (resp.data or []) if is_active_event(r)]
    clubs = {c["id"]: c["name"] for c in (
        db._c.table("clubs").select("id, name").execute().data or [])}
    out = []
    for r in rows:
        tdata = r.get("tournament_data") or {}
        out.append({
            "id": r["id"],
            "name": r.get("name", "Torneo"),
            "club_name": clubs.get(r.get("club_id"), "Club"),
            "start_date": r.get("start_date", ""),
            "end_date": r.get("end_date", ""),
            "registration_open": bool(tdata.get("registration_open")),
            "location": tdata.get("location", "") or "",
        })
    out.sort(key=lambda x: x["start_date"])
    return out


def list_active_phases_all() -> list[dict]:
    """Fases de ranking ACTIVAS de todos los clubs, con nombre de club."""
    db = get_db()
    resp = (db._c.table("ranking_phases")
            .select("id, club_id, name, start_date, end_date, is_active")
            .eq("is_active", True).execute())
    rows = [r for r in (resp.data or []) if is_active_event(r)]
    clubs = {c["id"]: c["name"] for c in (
        db._c.table("clubs").select("id, name").execute().data or [])}
    out = [{
        "id": r["id"],
        "name": r.get("name", "Ranking"),
        "club_name": clubs.get(r.get("club_id"), "Club"),
        "start_date": r.get("start_date", ""),
        "end_date": r.get("end_date", ""),
    } for r in rows]
    out.sort(key=lambda x: x["start_date"])
    return out
