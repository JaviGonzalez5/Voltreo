"""
Autenticación propia con bcrypt.
No usa Supabase Auth — gestiona usuarios en la tabla `users` con password_hash.

Roles:
  superadmin  — acceso a todos los clubs, gestión de clubs y usuarios
  club_admin  — acceso solo a los datos de su club
"""

from typing import Optional

import bcrypt
import streamlit as st

# Clave en session_state donde se almacena el usuario autenticado
_AUTH_KEY = "auth_user"


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
    for key in list(st.session_state.keys()):
        del st.session_state[key]
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
    st.markdown(
        """
        <style>
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], [data-testid="collapsedControl"], .stDeployButton {
            visibility: hidden !important;
            display: none !important;
        }
        header[data-testid="stHeader"] {
            background: transparent !important;
            height: 0 !important;
        }
        .stApp {
            background: #f3f7fb !important;
        }
        .main .block-container {
            max-width: 980px !important;
            padding-top: 5.5rem !important;
        }
        .login-shell {
            display: grid;
            grid-template-columns: 1fr 420px;
            gap: 2rem;
            align-items: stretch;
        }
        .login-panel {
            background: #ffffff;
            border: 1px solid #dfe9f4;
            border-bottom: 0;
            border-radius: 8px 8px 0 0;
            padding: 1.6rem 1.6rem .6rem;
            box-shadow: 0 16px 45px rgba(15,23,42,.08);
        }
        .login-brand {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            height: 42px;
            border-radius: 8px;
            background: linear-gradient(135deg,#00c47a,#007a73);
            color: white;
            font-weight: 900;
            margin-bottom: 1.1rem;
        }
        .login-copy {
            background: linear-gradient(135deg,#07121f,#0d2b37);
            border-radius: 8px;
            padding: 2rem;
            color: #eaf6ff;
            min-height: 100%;
        }
        .login-copy h1 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.12;
            letter-spacing: 0;
        }
        .login-copy p {
            color: #9eb6ce;
            line-height: 1.55;
            margin-top: .8rem;
        }
        .login-feature {
            margin-top: 1.2rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255,255,255,.10);
            color: #cfe0ee;
            font-size: .9rem;
        }
        .login-title {
            color: #0b1a2b;
            font-size: 1.35rem;
            font-weight: 850;
            margin-bottom: .25rem;
        }
        .login-subtitle {
            color: #657d95;
            font-size: .9rem;
            margin-bottom: 1.2rem;
        }
        [data-testid="stForm"] {
            background: #ffffff !important;
            border: 1px solid #dfe9f4 !important;
            border-top: 0 !important;
            border-radius: 8px !important;
            border-top-left-radius: 0 !important;
            border-top-right-radius: 0 !important;
            padding: .2rem 1.6rem 1.6rem !important;
            box-shadow: 0 16px 45px rgba(15,23,42,.08) !important;
        }
        .stButton > button {
            border-radius: 8px !important;
            background: linear-gradient(135deg,#08b86f,#078c83) !important;
            color: #fff !important;
            border: none !important;
            font-weight: 750 !important;
        }
        [data-testid="stTextInput"] input {
            border-radius: 8px !important;
            border-color: #dfe9f4 !important;
            background: #f8fbff !important;
        }
        @media (max-width: 900px) {
            .login-shell { grid-template-columns: 1fr; }
            .login-copy { min-height: auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.08, 1], gap="large")
    with left:
        st.markdown(
            """
            <section class="login-copy">
                <div class="login-brand">P+</div>
                <h1>PadelPlus Club</h1>
                <p>Organiza rankings, torneos, pistas y horarios desde un panel privado para cada club.</p>
                <div class="login-feature">Datos separados por club · Roles de administrador · Preparado para crecer</div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class="login-panel">
                <div class="login-title">Acceso al panel</div>
                <div class="login-subtitle">Introduce tus credenciales para continuar.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="tu_usuario")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
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
                st.rerun()

    st.stop()
