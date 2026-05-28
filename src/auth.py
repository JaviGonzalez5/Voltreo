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
    # CSS para centrar el formulario
    st.markdown(
        """
        <style>
        .login-wrap {
            max-width: 420px;
            margin: 6rem auto 0 auto;
        }
        .login-logo {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: .5rem;
        }
        .login-title {
            text-align: center;
            font-size: 1.4rem;
            font-weight: 700;
            color: #0b1a2b;
            margin-bottom: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-logo">🎾</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Ranking Pádel · Acceso</div>', unsafe_allow_html=True)

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
                    # Enriquecer con nombre del club
                    if user.get("club_id"):
                        club = db.get_club_by_id(user["club_id"])
                        user["club_name"] = club["name"] if club else ""
                    set_session_user(user)
                    st.rerun()

    st.stop()
