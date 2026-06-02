"""
Autenticación propia con bcrypt.
No usa Supabase Auth — gestiona usuarios en la tabla `users` con password_hash.

Roles:
  superadmin  — acceso a todos los clubs, gestión de clubs y usuarios
  club_admin  — acceso solo a los datos de su club
"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import bcrypt
import streamlit as st
try:
    import extra_streamlit_components as stx
except Exception:  # pragma: no cover - fallback si el componente no está instalado
    stx = None

# Clave en session_state donde se almacena el usuario autenticado
_AUTH_KEY = "auth_user"
_REMEMBER_COOKIE_NAME = "pp_remember"
_REMEMBER_DAYS = 30


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Genera un hash bcrypt de la contraseña."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Rate limiting (session-state; no requiere Redis)
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS  = 5          # intentos máximos antes de bloquear
_LOCKOUT_SECS  = 300        # 5 minutos de bloqueo

def _login_attempts_key() -> str:
    return "_login_attempts"

def _login_lockout_key() -> str:
    return "_login_locked_until"

def check_rate_limit() -> tuple[bool, int]:
    """
    Comprueba si el usuario actual está bloqueado por demasiados intentos fallidos.
    Retorna (bloqueado: bool, segundos_restantes: int).
    """
    import time as _time
    locked_until = st.session_state.get(_login_lockout_key(), 0)
    if locked_until and _time.time() < locked_until:
        remaining = int(locked_until - _time.time())
        return True, remaining
    return False, 0


def _record_failed_attempt() -> None:
    """Registra un intento fallido y aplica bloqueo si se supera el límite."""
    import time as _time
    key = _login_attempts_key()
    attempts = st.session_state.get(key, 0) + 1
    st.session_state[key] = attempts
    if attempts >= _MAX_ATTEMPTS:
        st.session_state[_login_lockout_key()] = _time.time() + _LOCKOUT_SECS
        st.session_state[key] = 0  # reset contador tras bloqueo


def _clear_login_attempts() -> None:
    st.session_state.pop(_login_attempts_key(), None)
    st.session_state.pop(_login_lockout_key(), None)


def _safe_get_secret(name: str) -> Optional[str]:
    """Lee una clave de st.secrets de forma segura (si existe)."""
    try:
        val = st.secrets.get(name)
        return str(val) if val else None
    except Exception:
        return None


def _auth_cookie_secret() -> Optional[str]:
    """
    Devuelve la clave usada para firmar tokens de sesión persistente.

    Prioridad:
    1) AUTH_COOKIE_SECRET (env / secrets)
    2) COOKIE_SECRET (env / secrets)
    3) SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY / SUPABASE_ANON_KEY (fallback)
    """
    for key in ("AUTH_COOKIE_SECRET", "COOKIE_SECRET"):
        val = os.environ.get(key) or _safe_get_secret(key) or _safe_get_secret(key.lower())
        if val:
            return val
    for key in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY"):
        val = os.environ.get(key) or _safe_get_secret(key) or _safe_get_secret(key.lower())
        if val:
            return val
    return None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign_token_payload(payload_b64: str, password_hash: str, secret: str) -> str:
    """
    Firma el payload usando HMAC-SHA256 y el hash de contraseña actual.
    Así, al cambiar contraseña, los tokens anteriores dejan de ser válidos.
    """
    msg = f"{payload_b64}|{password_hash}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _build_remember_token(user: dict) -> Optional[str]:
    secret = _auth_cookie_secret()
    if not secret:
        return None
    uid = user.get("id")
    usr = user.get("username")
    pwd_hash = user.get("password_hash", "")
    if not uid or not usr or not pwd_hash:
        return None
    exp = int((datetime.now(timezone.utc) + timedelta(days=_REMEMBER_DAYS)).timestamp())
    payload = {"uid": str(uid), "usr": str(usr).strip().lower(), "exp": exp}
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    sig = _sign_token_payload(payload_b64, str(pwd_hash), secret)
    return f"{payload_b64}.{sig}"


def _parse_remember_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload_b64, sig = token.split(".", 1)
        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None

    uid = payload.get("uid")
    usr = payload.get("usr")
    exp = payload.get("exp")
    if not uid or not usr or not isinstance(exp, int):
        return None
    return {"uid": uid, "usr": usr, "exp": exp, "payload_b64": payload_b64, "sig": sig}


def _cookie_manager():
    """
    Instancia del CookieManager (extra_streamlit_components).

    IMPORTANTE: debe llamarse INCONDICIONALMENTE al inicio de cada ciclo de
    renderizado (antes de cualquier st.stop()) para que el componente mantenga
    su posición estable en el árbol y pueda leer/escribir cookies del navegador.
    La clave fija ("_pp_cm") es obligatoria en versiones >= 0.1.60 para evitar
    colisiones de ID de componente.
    """
    if stx is None:
        return None
    mgr = st.session_state.get("_cookie_manager")
    if mgr is None:
        try:
            mgr = stx.CookieManager(key="_pp_cm")
        except TypeError:
            # Versiones muy antiguas no aceptan key=
            mgr = stx.CookieManager()
        st.session_state["_cookie_manager"] = mgr
    return mgr


def set_remember_cookie(user: dict) -> bool:
    """Guarda cookie persistente de login (30 días)."""
    token = _build_remember_token(user)
    mgr = _cookie_manager()
    if not token or mgr is None:
        return False
    expires_at = datetime.now(timezone.utc) + timedelta(days=_REMEMBER_DAYS)
    try:
        mgr.set(
            _REMEMBER_COOKIE_NAME,
            token,
            expires_at=expires_at,
            same_site="lax",
            secure=True,
        )
        return True
    except Exception:
        return False


def clear_remember_cookie() -> None:
    mgr = _cookie_manager()
    if mgr is None:
        return
    try:
        mgr.delete(_REMEMBER_COOKIE_NAME)
    except Exception:
        pass


def restore_session_from_cookie(db) -> bool:
    """
    Intenta restaurar sesión desde cookie persistente.
    Retorna True solo si la sesión queda autenticada.
    """
    if is_authenticated():
        return True

    secret = _auth_cookie_secret()
    mgr = _cookie_manager()
    if not secret or mgr is None:
        return False

    token = None
    try:
        token = mgr.get(_REMEMBER_COOKIE_NAME)
    except Exception:
        token = None

    # Fallback: algunos navegadores/componentes devuelven cookies solo vía get_all().
    if (not token or not isinstance(token, str)) and hasattr(mgr, "get_all"):
        try:
            all_cookies = mgr.get_all() or {}
            if isinstance(all_cookies, dict):
                token = all_cookies.get(_REMEMBER_COOKIE_NAME)
        except Exception:
            token = token

    if not token or not isinstance(token, str):
        return False

    parsed = _parse_remember_token(token)
    if not parsed:
        # Evita borrar una cookie potencialmente válida si el componente
        # aún no devolvió el valor completo en este render.
        if "." in token:
            clear_remember_cookie()
        return False

    if parsed["exp"] <= int(datetime.now(timezone.utc).timestamp()):
        clear_remember_cookie()
        return False

    user = db.get_user_by_username(str(parsed["usr"]).strip().lower())
    if not user or not user.get("is_active", True):
        clear_remember_cookie()
        return False
    if str(user.get("id")) != str(parsed["uid"]):
        clear_remember_cookie()
        return False

    expected_sig = _sign_token_payload(parsed["payload_b64"], str(user.get("password_hash", "")), secret)
    if not hmac.compare_digest(str(parsed["sig"]), expected_sig):
        clear_remember_cookie()
        return False

    if user.get("club_id"):
        club = db.get_club_by_id(user["club_id"])
        user["club_name"] = club["name"] if club else ""

    set_session_user(user)
    # Sliding expiration: renueva la cookie al restaurar sesión.
    set_remember_cookie(user)
    return True


def validate_password_strength(password: str) -> list[str]:
    """
    Valida que la contraseña cumple los requisitos mínimos.
    Retorna lista de errores (vacía = contraseña válida).
    """
    errors = []
    if len(password) < 8:
        errors.append("Mínimo 8 caracteres.")
    if not any(c.isupper() for c in password):
        errors.append("Al menos una mayúscula.")
    if not any(c.isdigit() for c in password):
        errors.append("Al menos un número.")
    return errors


def login(db, username: str, password: str) -> Optional[dict]:
    """
    Verifica credenciales con rate limiting incorporado.

    Retorna el dict del usuario si OK.
    Retorna None si usuario no existe, inactivo, o contraseña incorrecta.
    Lanza RuntimeError si la sesión está bloqueada por demasiados intentos.
    """
    blocked, secs = check_rate_limit()
    if blocked:
        raise RuntimeError(f"Demasiados intentos. Espera {secs}s.")

    user = db.get_user_by_username(username.strip().lower())
    if user is None:
        _record_failed_attempt()
        return None
    if not user.get("is_active", True):
        _record_failed_attempt()
        return None
    if not verify_password(password, user["password_hash"]):
        _record_failed_attempt()
        return None

    _clear_login_attempts()  # login OK → resetear contador
    return user


def logout() -> None:
    """Elimina el usuario de la sesión y recarga la app."""
    clear_remember_cookie()
    # Preservar el CookieManager para que siga funcionando después del logout.
    _mgr = st.session_state.get("_cookie_manager")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if _mgr is not None:
        st.session_state["_cookie_manager"] = _mgr
    # _logout_done bloquea restore_session_from_cookie durante los ciclos de
    # rerun post-logout. Sin este flag, el warmup lanza 2 reruns adicionales y
    # la cookie (aún no borrada por el JS del browser) vuelve a loguear al usuario.
    st.session_state["_logout_done"] = True
    # Resetear el warmup para que el próximo login funcione correctamente.
    st.session_state["_cookie_warmup"] = 0
    st.rerun()


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------

def set_session_user(user: dict) -> None:
    """Guarda el usuario autenticado en session_state."""
    st.session_state[_AUTH_KEY] = {
        "user_id":      user["id"],
        "username":     user["username"],
        "display_name": user.get("display_name") or user["username"],
        "role":         user["role"],
        "club_id":      user.get("club_id"),  # None para superadmin
        "club_name":    user.get("club_name", ""),
    }


def get_session_user() -> Optional[dict]:
    """Devuelve el usuario de la sesión actual o None si no está autenticado."""
    return st.session_state.get(_AUTH_KEY)


def is_authenticated() -> bool:
    return _AUTH_KEY in st.session_state


def is_superadmin() -> bool:
    u = get_session_user()
    return u is not None and u["role"] == "superadmin"


def current_club_id() -> Optional[str]:
    """
    Devuelve el club_id activo:
    - Para club_admin: su club_id propio.
    - Para superadmin: el club seleccionado en el selector (o None si no ha elegido).
    """
    u = get_session_user()
    if u is None:
        return None
    if u["role"] == "superadmin":
        return st.session_state.get("superadmin_selected_club_id")
    return u["club_id"]


def current_club_name() -> str:
    u = get_session_user()
    if u is None:
        return ""
    if u["role"] == "superadmin":
        return st.session_state.get("superadmin_selected_club_name", "— Sin club seleccionado —")
    return u.get("club_name", "")


# ---------------------------------------------------------------------------
# UI: landing pública (antes del login)
# ---------------------------------------------------------------------------

def render_landing_screen() -> None:
    """
    Página de marketing pública. Muestra las características de Voltreo
    y un CTA de acceso. No requiere BD — funciona siempre.
    Llama a st.stop() al final.
    """
    from .branding import (
        BRAND_NAME, BRAND_MONOGRAM, BRAND_GRADIENT,
        BRAND_HEADLINE, BRAND_SUBHEAD, BRAND_PITCH, BRAND_BETA_MSG, BRAND_CONTACT,
    )
    from html import escape as _esc

    st.markdown(
        f"""
        <style>
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], [data-testid="collapsedControl"],
        .stDeployButton, [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {{
            display: none !important;
        }}
        header[data-testid="stHeader"] {{ display: none !important; }}

        .stApp {{ background: #f7f7f5 !important; }}
        .main .block-container {{
            max-width: 1100px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }}

        /* ── Nav ───────────────────────────────────────────────────── */
        .lp-nav {{
            display: flex; align-items: center; justify-content: space-between;
            padding: 1.1rem 0; margin-bottom: .5rem;
        }}
        .lp-logo {{ display: flex; align-items: center; gap: .6rem; }}
        .lp-logo-mark {{
            width: 34px; height: 34px; border-radius: 9px;
            background: {BRAND_GRADIENT};
            display: flex; align-items: center; justify-content: center;
            color: #fff; font-weight: 900; font-size: .95rem;
            box-shadow: 0 3px 12px rgba(0,200,83,.35);
        }}
        .lp-logo-name {{ font-size: 1.05rem; font-weight: 800; color: #0b1a2b; letter-spacing: -.01em; }}
        .lp-logo-sub  {{ font-size: .65rem; color: #94a8be; text-transform: uppercase; letter-spacing: .12em; }}

        /* ── Hero ───────────────────────────────────────────────────── */
        .lp-hero {{
            padding: 4rem 0 3.5rem;
            display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; align-items: center;
        }}
        .lp-badge {{
            display: inline-flex; align-items: center; gap: .4rem;
            background: rgba(0,200,83,.10); border: 1px solid rgba(0,200,83,.28);
            border-radius: 20px; padding: .22rem .85rem;
            font-size: .72rem; font-weight: 800; letter-spacing: .1em;
            text-transform: uppercase; color: #00843d; margin-bottom: .9rem;
        }}
        .lp-h1 {{
            font-size: 2.6rem; font-weight: 850; color: #07111d;
            line-height: 1.12; letter-spacing: -.03em; margin: 0 0 1rem;
        }}
        .lp-h1 .accent {{ color: #00843d; }}
        .lp-sub {{ font-size: 1.05rem; color: #5d7a96; line-height: 1.6; margin: 0 0 2rem; max-width: 480px; }}
        .lp-cta-row {{ display: flex; gap: .8rem; flex-wrap: wrap; }}
        .lp-btn-pri {{
            display: inline-flex; align-items: center; gap: .4rem;
            background: {BRAND_GRADIENT}; color: #fff;
            border: none; border-radius: 10px; padding: .7rem 1.6rem;
            font-size: .92rem; font-weight: 700; cursor: pointer; text-decoration: none;
            box-shadow: 0 4px 16px rgba(0,200,83,.35);
        }}
        .lp-btn-sec {{
            display: inline-flex; align-items: center;
            background: #fff; color: #0b1a2b;
            border: 1.5px solid #d8e8f4; border-radius: 10px; padding: .7rem 1.6rem;
            font-size: .92rem; font-weight: 600; cursor: pointer; text-decoration: none;
        }}
        .lp-stats {{ display: flex; gap: 2rem; margin-top: 2.5rem; flex-wrap: wrap; }}
        .lp-stat-n {{ font-size: 1.5rem; font-weight: 850; color: #07111d; line-height: 1; }}
        .lp-stat-l {{ font-size: .75rem; color: #7088a0; margin-top: .15rem; }}

        /* ── Mock widget ────────────────────────────────────────────── */
        .lp-widget {{
            background: #07111d; border-radius: 18px; padding: 1.4rem 1.6rem;
            box-shadow: 0 20px 60px rgba(7,17,29,.35), 0 4px 16px rgba(0,0,0,.15);
        }}
        .lp-widget-label {{
            font-size: .62rem; font-weight: 800; letter-spacing: .14em;
            text-transform: uppercase; color: #00c853; margin-bottom: .8rem;
        }}
        .lp-widget-row {{
            display: flex; align-items: center; justify-content: space-between;
            padding: .55rem .6rem; border-radius: 8px; margin-bottom: .3rem;
            background: rgba(255,255,255,.04);
        }}
        .lp-widget-row:first-of-type {{ background: rgba(0,200,83,.14); }}
        .lp-widget-pos {{ color: #4a7aa0; font-size: .8rem; font-weight: 700; width: 20px; }}
        .lp-widget-name {{ color: #e8f4ff; font-size: .88rem; font-weight: 600; flex: 1; margin-left: .5rem; }}
        .lp-widget-pts {{ color: #7fffc0; font-size: .82rem; font-weight: 700; }}
        .lp-widget-tag {{
            font-size: .62rem; font-weight: 800; letter-spacing: .06em;
            background: rgba(0,200,83,.18); color: #7fffc0; border-radius: 6px;
            padding: .2rem .5rem; margin-top: .8rem; display: inline-block;
        }}

        /* ── Features ───────────────────────────────────────────────── */
        .lp-section {{ padding: 4rem 0; }}
        .lp-section-label {{
            font-size: .7rem; font-weight: 800; letter-spacing: .14em;
            text-transform: uppercase; color: #00843d; margin-bottom: .5rem;
        }}
        .lp-section-title {{ font-size: 2rem; font-weight: 850; color: #07111d; margin: 0 0 .5rem; letter-spacing: -.02em; }}
        .lp-section-sub {{ font-size: 1rem; color: #5d7a96; margin-bottom: 2.5rem; }}
        .lp-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; }}
        .lp-card {{
            background: #fff; border: 1px solid #e2eaf4; border-radius: 14px;
            padding: 1.3rem 1.4rem;
            box-shadow: 0 1px 4px rgba(11,26,43,.05);
            transition: box-shadow .15s, transform .15s;
        }}
        .lp-card:hover {{ box-shadow: 0 6px 20px rgba(11,26,43,.10); transform: translateY(-2px); }}
        .lp-card-icon {{ font-size: 1.5rem; margin-bottom: .6rem; }}
        .lp-card-title {{ font-size: .95rem; font-weight: 800; color: #07111d; margin-bottom: .35rem; }}
        .lp-card-text {{ font-size: .85rem; color: #5d7a96; line-height: 1.5; }}

        /* ── Why section ────────────────────────────────────────────── */
        .lp-why {{
            background: #07111d; border-radius: 20px; padding: 3rem 3.5rem;
            margin: 2rem 0; display: grid; grid-template-columns: 1fr 1fr; gap: 3rem;
        }}
        .lp-why h2 {{ font-size: 1.8rem; font-weight: 850; color: #fff; margin: 0 0 .8rem; letter-spacing: -.02em; }}
        .lp-why p {{ color: #9ec0dc; font-size: .95rem; line-height: 1.65; }}
        .lp-check {{ display: flex; align-items: flex-start; gap: .6rem; margin-top: .9rem; }}
        .lp-check-dot {{
            width: 20px; height: 20px; border-radius: 6px; flex-shrink: 0; margin-top: .1rem;
            background: rgba(0,200,83,.18); border: 1px solid rgba(0,200,83,.35);
            display: flex; align-items: center; justify-content: center;
            font-size: .65rem; color: #7fffc0;
        }}
        .lp-check-text {{ color: #cfe2f2; font-size: .9rem; line-height: 1.4; }}

        /* ── Pricing ────────────────────────────────────────────────── */
        .lp-pricing {{
            text-align: center; background: #fff; border: 1px solid #e2eaf4;
            border-radius: 20px; padding: 3rem; margin: 2rem 0;
            box-shadow: 0 4px 24px rgba(11,26,43,.07);
        }}
        .lp-pricing h2 {{ font-size: 1.8rem; font-weight: 850; color: #07111d; margin: 0 0 .5rem; }}
        .lp-pricing p {{ font-size: 1rem; color: #5d7a96; max-width: 480px; margin: 0 auto 1.8rem; }}
        .lp-pricing-note {{
            font-size: .8rem; color: #94a8be; margin-top: 1.2rem;
        }}

        /* ── Footer ─────────────────────────────────────────────────── */
        .lp-footer {{
            text-align: center; padding: 2.5rem 0;
            border-top: 1px solid #e8f0f8; color: #94a8be; font-size: .82rem;
        }}

        @media (max-width: 850px) {{
            .lp-hero {{ grid-template-columns: 1fr; gap: 2rem; padding: 2.5rem 0; }}
            .lp-why {{ grid-template-columns: 1fr; }}
            .lp-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
        @media (max-width: 550px) {{
            .lp-grid {{ grid-template-columns: 1fr; }}
            .lp-h1 {{ font-size: 2rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Navbar ──────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="lp-nav">'
        f'<div class="lp-logo">'
        f'<div class="lp-logo-mark">{_esc(BRAND_MONOGRAM)}</div>'
        f'<div><div class="lp-logo-name">{_esc(BRAND_NAME)}</div>'
        f'<div class="lp-logo-sub">Sports Manager</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="lp-hero">'
        # Izquierda
        f'<div>'
        f'<div class="lp-badge">✦ Software para clubes</div>'
        f'<h1 class="lp-h1">{_esc(BRAND_HEADLINE.replace("profesional.", ""))}'
        f'<span class="accent">profesional.</span></h1>'
        f'<p class="lp-sub">{_esc(BRAND_SUBHEAD)}</p>'
        f'<div class="lp-stats">'
        f'<div><div class="lp-stat-n">3+</div><div class="lp-stat-l">Deportes</div></div>'
        f'<div><div class="lp-stat-n">100%</div><div class="lp-stat-l">Aislamiento por club</div></div>'
        f'<div><div class="lp-stat-n">&lt;5 min</div><div class="lp-stat-l">Primer torneo</div></div>'
        f'</div></div>'
        # Derecha — mock ranking widget
        f'<div class="lp-widget">'
        f'<div class="lp-widget-label">📊 Ranking · Top jugadores</div>'
        f'<div class="lp-widget-row"><span class="lp-widget-pos">1</span><span class="lp-widget-name">Lucía Hernández</span><span class="lp-widget-pts">1 240 pts</span></div>'
        f'<div class="lp-widget-row"><span class="lp-widget-pos">2</span><span class="lp-widget-name">Marta Ruiz</span><span class="lp-widget-pts">1 115 pts</span></div>'
        f'<div class="lp-widget-row"><span class="lp-widget-pos">3</span><span class="lp-widget-name">David Pérez</span><span class="lp-widget-pts">980 pts</span></div>'
        f'<div class="lp-widget-row"><span class="lp-widget-pos">4</span><span class="lp-widget-name">Carlos Vidal</span><span class="lp-widget-pts">870 pts</span></div>'
        f'<div class="lp-widget-tag">Actualizado automáticamente ✓</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Botones CTA del hero — st.button() reales (no href) para no salir de la página
    _h1, _h2, _h3 = st.columns([2, 2, 4])
    with _h1:
        if st.button("🔑  Acceder al panel", type="primary", use_container_width=True, key="lp_login_hero"):
            st.session_state["_show_login"] = True
            st.rerun()
    with _h2:
        st.link_button("✉️  Solicitar acceso", f"mailto:{BRAND_CONTACT}", use_container_width=True)

    # ── Features grid ────────────────────────────────────────────────────────
    st.markdown(
        '<div class="lp-section">'
        '<div class="lp-section-label">Funcionalidades</div>'
        '<h2 class="lp-section-title">Todo lo que tu club necesita.<br>Nada más.</h2>'
        '<p class="lp-section-sub">Sin hojas de cálculo, sin WhatsApp caótico, sin errores de planificación.</p>'
        '<div class="lp-grid">'
        '<div class="lp-card"><div class="lp-card-icon">🏆</div>'
        '<div class="lp-card-title">Rankings en vivo</div>'
        '<div class="lp-card-text">Clasificaciones automáticas por jugadores o parejas. Se actualizan solos al registrar resultados.</div></div>'
        '<div class="lp-card"><div class="lp-card-icon">🎾</div>'
        '<div class="lp-card-title">Torneos profesionales</div>'
        '<div class="lp-card-text">Grupos + cuadro eliminatorio en segundos. Bracket visual, resultados y avance automático.</div></div>'
        '<div class="lp-card"><div class="lp-card-icon">🗓️</div>'
        '<div class="lp-card-title">Calendario sin solapamientos</div>'
        '<div class="lp-card-text">Asigna pistas y horarios con validaciones automáticas. Nadie juega dos partidos a la vez.</div></div>'
        '<div class="lp-card"><div class="lp-card-icon">🌐</div>'
        '<div class="lp-card-title">Multi-club y multi-deporte</div>'
        '<div class="lp-card-text">Pádel, pickleball o ambos. Cada club con sus propios datos, jugadores y permisos.</div></div>'
        '<div class="lp-card"><div class="lp-card-icon">📤</div>'
        '<div class="lp-card-title">Exportación y enlace público</div>'
        '<div class="lp-card-text">Descarga el calendario en Excel o comparte un enlace directo para que los jugadores vean su horario.</div></div>'
        '<div class="lp-card"><div class="lp-card-icon">🔒</div>'
        '<div class="lp-card-title">Datos seguros, por diseño</div>'
        '<div class="lp-card-text">Aislamiento por club, sesiones cifradas y permisos por rol. Lo que esperas de un software serio.</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # ── Why Voltreo ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="lp-why">'
        '<div>'
        '<h2>Tu Excel no era el problema.<br>El proceso, sí.</h2>'
        '<p>Cada semana: calcular rankings a mano, buscar huecos en pistas, '
        'avisar por WhatsApp a 60 jugadores. Voltreo lo automatiza todo.</p>'
        '</div>'
        '<div>'
        '<div class="lp-check"><div class="lp-check-dot">✓</div>'
        '<div class="lp-check-text">Cuadros de torneo generados en segundos</div></div>'
        '<div class="lp-check"><div class="lp-check-dot">✓</div>'
        '<div class="lp-check-text">Ranking recalculado tras cada resultado</div></div>'
        '<div class="lp-check"><div class="lp-check-dot">✓</div>'
        '<div class="lp-check-text">Horarios comprimidos sin solapamientos</div></div>'
        '<div class="lp-check"><div class="lp-check-dot">✓</div>'
        '<div class="lp-check-text">Enlace público compartible para jugadores</div></div>'
        '<div class="lp-check"><div class="lp-check-dot">✓</div>'
        '<div class="lp-check-text">Roles y permisos por club</div></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Pricing (acceso por invitación) ──────────────────────────────────────
    st.markdown(
        f'<div class="lp-pricing">'
        f'<div class="lp-section-label">ACCESO</div>'
        f'<h2>Gratis durante la beta.</h2>'
        f'<p>Estamos creciendo con clubes reales. El acceso es por invitación '
        f'para garantizar la calidad del servicio.</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Botones del pricing como st.button() reales
    _p1, _p2, _p3 = st.columns([1, 2, 2])
    with _p2:
        if st.button("🔑  Acceder al panel", type="primary", use_container_width=True, key="lp_login_pricing"):
            st.session_state["_show_login"] = True
            st.rerun()
    with _p3:
        st.link_button("✉️  Solicitar invitación", f"mailto:{BRAND_CONTACT}", use_container_width=True)

    # ── Footer ───────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="lp-footer">'
        f'<strong>{_esc(BRAND_NAME)}</strong> · Sports Manager &nbsp;|&nbsp; '
        f'{BRAND_PITCH} &nbsp;|&nbsp; '
        f'<a href="mailto:{BRAND_CONTACT}" style="color:#94a8be">{BRAND_CONTACT}</a>'
        f'<br>© 2026 {_esc(BRAND_NAME)}'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.stop()


# ---------------------------------------------------------------------------
# UI: pantalla de login
# ---------------------------------------------------------------------------

def render_login_screen(db) -> None:
    """
    Muestra la pantalla de login centrada.
    Llama a st.stop() internamente para detener el renderizado del resto de la app.
    """
    # Segundo intento de restauración: el gestor de cookies puede no estar listo
    # en el primer ciclo de render.
    if not is_authenticated() and restore_session_from_cookie(db):
        st.rerun()

    from .branding import (
        BRAND_NAME, BRAND_MONOGRAM, BRAND_SUFFIX, BRAND_TAGLINE, BRAND_PITCH, BRAND_GRADIENT,
    )
    st.markdown(
        f"""
        <style>
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], [data-testid="collapsedControl"], .stDeployButton {{
            visibility: hidden !important; display: none !important;
        }}
        header[data-testid="stHeader"] {{ background: transparent !important; height: 0 !important; }}
        /* Fondo de marca con destellos sutiles */
        .stApp {{
            background:
                radial-gradient(900px 500px at 12% -10%, rgba(0,200,83,.10), transparent 60%),
                radial-gradient(800px 500px at 100% 110%, rgba(0,137,123,.10), transparent 55%),
                #0a1622 !important;
        }}
        .main .block-container {{ max-width: 1060px !important; padding-top: 4.5rem !important; }}

        /* ── Columna izquierda: marca ─────────────────────────────────── */
        .lv-hero {{ padding: 1.5rem .5rem; }}
        .lv-logo-row {{ display:flex; align-items:center; gap:.85rem; margin-bottom:2.2rem; }}
        .lv-logo {{
            width:52px; height:52px; border-radius:15px;
            background:{BRAND_GRADIENT};
            display:flex; align-items:center; justify-content:center;
            font-size:1.7rem; font-weight:900; color:#fff;
            box-shadow:0 8px 30px rgba(0,200,83,.45), inset 0 1px 0 rgba(255,255,255,.3);
        }}
        .lv-logo-txt b {{ color:#eaf6ff; font-size:1.45rem; font-weight:850; letter-spacing:-.02em; display:block; line-height:1; }}
        .lv-logo-txt span {{ color:#4a7aa0; font-size:.72rem; letter-spacing:.18em; text-transform:uppercase; }}
        .lv-hero h1 {{
            color:#fff; font-size:2.5rem; font-weight:850; line-height:1.1;
            letter-spacing:-.03em; margin:0 0 1rem;
        }}
        .lv-hero h1 .grad {{
            background:{BRAND_GRADIENT}; -webkit-background-clip:text;
            background-clip:text; -webkit-text-fill-color:transparent;
        }}
        .lv-hero p {{ color:#9ec0dc; font-size:1.02rem; line-height:1.6; max-width:460px; margin:0 0 1.8rem; }}
        .lv-feats {{ display:flex; flex-direction:column; gap:.7rem; }}
        .lv-feat {{ display:flex; align-items:center; gap:.6rem; color:#cfe2f2; font-size:.92rem; }}
        .lv-feat .dot {{
            width:22px; height:22px; border-radius:7px; flex-shrink:0;
            background:rgba(0,200,83,.16); border:1px solid rgba(0,200,83,.3);
            display:flex; align-items:center; justify-content:center; font-size:.7rem; color:#7fffc0;
        }}
        .lv-pitch {{
            margin-top:1.8rem; padding-top:1.2rem; border-top:1px solid rgba(255,255,255,.08);
            color:#5a82a4; font-size:.82rem; letter-spacing:.02em;
        }}

        /* ── Columna derecha: tarjeta de acceso ───────────────────────── */
        .lv-card-head {{
            background:#fff; border:1px solid #e6eef8; border-bottom:0;
            border-radius:18px 18px 0 0; padding:1.7rem 1.8rem .4rem;
            box-shadow:0 30px 70px rgba(0,0,0,.35);
        }}
        .lv-card-head .t {{ color:#0b1a2b; font-size:1.4rem; font-weight:850; }}
        .lv-card-head .s {{ color:#6b86a4; font-size:.9rem; margin-top:.2rem; }}
        [data-testid="stForm"] {{
            background:#fff !important; border:1px solid #e6eef8 !important; border-top:0 !important;
            border-radius:0 0 18px 18px !important;
            padding:.4rem 1.8rem 1.8rem !important;
            box-shadow:0 30px 70px rgba(0,0,0,.35) !important;
        }}
        [data-testid="stForm"] label {{ color:#3d5a78 !important; font-weight:600 !important; font-size:.85rem !important; }}
        [data-testid="stTextInput"] input {{
            border-radius:10px !important; border-color:#dbe7f4 !important;
            background:#f8fbff !important; padding:.6rem .8rem !important;
        }}
        [data-testid="stTextInput"] input:focus {{
            border-color:#00c853 !important; box-shadow:0 0 0 3px rgba(0,200,83,.14) !important;
        }}
        .stButton > button {{
            border-radius:11px !important; background:{BRAND_GRADIENT} !important;
            color:#fff !important; border:none !important; font-weight:750 !important;
            padding:.6rem !important; box-shadow:0 6px 20px rgba(0,200,83,.4) !important;
            transition:transform .15s, box-shadow .15s !important;
        }}
        .stButton > button:hover {{ transform:translateY(-2px) !important; box-shadow:0 10px 28px rgba(0,200,83,.5) !important; }}
        [data-testid="stCheckbox"] label {{ color:#5d7a96 !important; font-size:.85rem !important; }}
        @media (max-width: 900px) {{ .lv-hero {{ padding-bottom:0; }} .lv-hero h1 {{ font-size:2rem; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown(
            f"""
            <section class="lv-hero">
                <div class="lv-logo-row">
                    <div class="lv-logo">{BRAND_MONOGRAM}</div>
                    <div class="lv-logo-txt"><b>{BRAND_NAME}</b><span>{BRAND_SUFFIX}</span></div>
                </div>
                <h1>Gestiona tu club como un <span class="grad">profesional</span></h1>
                <p>{BRAND_TAGLINE}</p>
                <div class="lv-feats">
                    <div class="lv-feat"><span class="dot">✓</span> Rankings automáticos con clasificación en vivo</div>
                    <div class="lv-feat"><span class="dot">✓</span> Torneos con grupos, cuadros y categorías</div>
                    <div class="lv-feat"><span class="dot">✓</span> Horarios y pistas sin solapamientos</div>
                    <div class="lv-feat"><span class="dot">✓</span> Datos privados y separados por club</div>
                </div>
                <div class="lv-pitch">{BRAND_PITCH}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class="lv-card-head">
                <div class="t">Acceso al panel</div>
                <div class="s">Introduce tus credenciales para continuar.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="tu_usuario")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            remember_me = st.checkbox("Mantener sesión iniciada (30 días)", value=True)
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    # Mostrar estado de bloqueo antes de procesar el form
    _blocked, _secs = check_rate_limit()
    if _blocked:
        st.error(f"🔒 Demasiados intentos fallidos. Espera **{_secs} segundos** antes de volver a intentarlo.")

    if submitted:
        if not username or not password:
            st.error("Introduce usuario y contraseña.")
        else:
            try:
                user = login(db, username, password)
            except RuntimeError as _e:
                st.error(str(_e))
                user = None

            if user is None and not _blocked:
                _remaining_attempts = _MAX_ATTEMPTS - st.session_state.get(_login_attempts_key(), 0)
                if _remaining_attempts > 0:
                    st.error(f"Usuario o contraseña incorrectos. ({_remaining_attempts} intentos restantes)")
                else:
                    st.error("Cuenta bloqueada temporalmente.")
            elif user is not None:
                if user.get("club_id"):
                    club = db.get_club_by_id(user["club_id"])
                    user["club_name"] = club["name"] if club else ""
                set_session_user(user)
                if remember_me:
                    set_remember_cookie(user)
                else:
                    clear_remember_cookie()
                st.rerun()

    st.stop()
