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
    # Preservar el CookieManager y el contador de warmup para que el próximo
    # intento de login pueda leer la cookie en el primer ciclo.
    _mgr = st.session_state.get("_cookie_manager")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if _mgr is not None:
        st.session_state["_cookie_manager"] = _mgr
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
