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

def login(db, username: str, password: str) -> Optional[dict]:
    """
    Verifica credenciales contra la base de datos.

    Retorna el dict del usuario si las credenciales son correctas,
    None si el usuario no existe, está inactivo o la contraseña es incorrecta.
    """
    user = db.get_user_by_username(username.strip().lower())
    if user is None:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
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

    if submitted:
        if not username or not password:
            st.error("Introduce usuario y contraseña.")
        else:
            user = login(db, username, password)
            if user is None:
                st.error("Usuario o contraseña incorrectos.")
            else:
                if user.get("club_id"):
                    club = db.get_club_by_id(user["club_id"])
                    user["club_name"] = club["name"] if club else ""
                set_session_user(user)
                st.rerun()

    st.stop()
