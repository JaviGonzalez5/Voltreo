"""
Capa de acceso a datos — Supabase (PostgreSQL).

Principio de diseño:
  · Esta capa NO conoce nada de Streamlit ni del scheduler.
  · Solo hace CRUD sobre las tablas: clubs, users, ranking_phases, tournaments.
  · Los modelos Pydantic se serializan/deserializan con .model_dump() / model_validate().
  · El cliente Supabase se cachea a nivel de proceso con @st.cache_resource.

Configuración necesaria (en .streamlit/secrets.toml o variables de entorno):
  SUPABASE_URL = "https://xxxx.supabase.co"
  SUPABASE_KEY = "eyJ..."   ← service role key (para operaciones server-side)
"""

import os
from datetime import datetime
from typing import Optional, Any

# supabase-py ≥ 2.0
from supabase import create_client, Client
import streamlit as st


# ---------------------------------------------------------------------------
# Cliente (singleton cacheado)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    """
    Crea el cliente Supabase una sola vez por proceso de Streamlit.
    Lee credenciales de st.secrets (Streamlit Cloud) o variables de entorno.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL y SUPABASE_KEY. "
            "Configúralos en .streamlit/secrets.toml o como variables de entorno."
        )
    return create_client(url, key)


def get_db() -> "SupabaseDB":
    """Devuelve una instancia de SupabaseDB lista para usar."""
    return SupabaseDB(_get_client())


def is_db_configured() -> bool:
    """Comprueba si las credenciales de Supabase están disponibles."""
    try:
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
        return bool(url and key)
    except Exception:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        return bool(url and key)


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class SupabaseDB:

    def __init__(self, client: Client):
        self._c = client

    # ================================================================
    # CLUBS
    # ================================================================

    def list_clubs(self) -> list[dict]:
        """Devuelve todos los clubs ordenados por nombre."""
        resp = self._c.table("clubs").select("*").order("name").execute()
        return resp.data or []

    def get_club_by_id(self, club_id: str) -> Optional[dict]:
        resp = self._c.table("clubs").select("*").eq("id", club_id).execute()
        return resp.data[0] if resp.data else None

    def get_club_by_slug(self, slug: str) -> Optional[dict]:
        resp = self._c.table("clubs").select("*").eq("slug", slug).execute()
        return resp.data[0] if resp.data else None

    def create_club(self, name: str, slug: str) -> dict:
        resp = self._c.table("clubs").insert({"name": name, "slug": slug}).execute()
        return resp.data[0]

    def delete_club(self, club_id: str) -> None:
        self._c.table("clubs").delete().eq("id", club_id).execute()

    # ================================================================
    # USERS
    # ================================================================

    def get_user_by_username(self, username: str) -> Optional[dict]:
        resp = (
            self._c.table("users")
            .select("*")
            .eq("username", username.strip().lower())
            .execute()
        )
        return resp.data[0] if resp.data else None

    def list_users(self, club_id: Optional[str] = None) -> list[dict]:
        """Lista usuarios. Si club_id es None, devuelve todos (para superadmin)."""
        q = self._c.table("users").select("*")
        if club_id is not None:
            q = q.eq("club_id", club_id)
        resp = q.order("username").execute()
        return resp.data or []

    _VALID_ROLES = {"superadmin", "club_admin"}

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str,
        club_id: Optional[str] = None,
        display_name: str = "",
        email: str = "",
    ) -> dict:
        if role not in self._VALID_ROLES:
            raise ValueError(f"Rol inválido: {role!r}. Debe ser uno de {self._VALID_ROLES}")
        payload = {
            "username":      username.strip().lower(),
            "password_hash": password_hash,
            "role":          role,
            "club_id":       club_id,
            "display_name":  display_name,
            "email":         email,
        }
        # is_active puede no existir si la migración no se ejecutó — se intenta primero con ella
        try:
            resp = self._c.table("users").insert({**payload, "is_active": True}).execute()
        except Exception:
            resp = self._c.table("users").insert(payload).execute()
        return resp.data[0]

    def update_user_password(self, user_id: str, new_hash: str) -> None:
        self._c.table("users").update({"password_hash": new_hash}).eq("id", user_id).execute()

    _UNSET = object()

    def update_user(
        self,
        user_id: str,
        *,
        role: Optional[str] = None,
        club_id: Any = _UNSET,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        """
        Actualiza campos de un usuario existente.

        Notas:
        - `club_id=_UNSET` => no toca el club.
        - `club_id=None`   => limpia el club (útil para superadmin).
        """
        payload: dict[str, Any] = {}
        if role is not None:
            if role not in self._VALID_ROLES:
                raise ValueError(f"Rol inválido: {role!r}. Debe ser uno de {self._VALID_ROLES}")
            payload["role"] = role
        if club_id is not self._UNSET:
            payload["club_id"] = club_id
        if display_name is not None:
            payload["display_name"] = display_name
        if email is not None:
            payload["email"] = email

        if not payload:
            return
        self._c.table("users").update(payload).eq("id", user_id).execute()

    def set_user_active(self, user_id: str, active: bool) -> None:
        self._c.table("users").update({"is_active": active}).eq("id", user_id).execute()

    def delete_user(self, user_id: str) -> None:
        self._c.table("users").delete().eq("id", user_id).execute()

    # ================================================================
    # RANKING PHASES
    # ================================================================

    def list_phases(self, club_id: str) -> list[dict]:
        """Lista fases de un club ordenadas por fecha de creación (más reciente primero)."""
        resp = (
            self._c.table("ranking_phases")
            .select("id, name, start_date, end_date, is_active, created_at, updated_at")
            .eq("club_id", club_id)
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []

    def get_phase(self, phase_id: str, club_id: str) -> Optional[dict]:
        """Carga una fase completa (con todos sus JSONB)."""
        resp = (
            self._c.table("ranking_phases")
            .select("*")
            .eq("id", phase_id)
            .eq("club_id", club_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_active_phase(self, club_id: str) -> Optional[dict]:
        """Carga la fase activa de un club (la más reciente con is_active=true)."""
        resp = (
            self._c.table("ranking_phases")
            .select("*")
            .eq("club_id", club_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def upsert_phase(
        self,
        club_id:         str,
        name:            str,
        start_date:      str,   # ISO date string "2026-06-01"
        end_date:        str,
        phase_config:    dict,
        groups_data:     list,
        bookings_data:   list,
        schedule_result: Optional[dict],
        phase_id:        Optional[str] = None,
    ) -> dict:
        """
        Crea o actualiza una fase. Si phase_id es None, crea una nueva.
        Devuelve el registro completo.
        """
        payload: dict[str, Any] = {
            "club_id":         club_id,
            "name":            name,
            "start_date":      start_date,
            "end_date":        end_date,
            "phase_config":    phase_config,
            "groups_data":     groups_data,
            "bookings_data":   bookings_data,
            "schedule_result": schedule_result,
            "is_active":       True,
        }
        if phase_id:
            payload["id"] = phase_id

        resp = self._c.table("ranking_phases").upsert(payload).execute()
        saved = resp.data[0]

        # Siempre desactivar las otras fases del club (INSERT y UPDATE)
        # Evita que múltiples fases queden is_active=True al guardar una existente
        self._c.table("ranking_phases").update({"is_active": False}).eq(
            "club_id", club_id
        ).neq("id", saved["id"]).execute()

        return saved

    def set_phase_active(self, phase_id: str, club_id: str) -> None:
        """Activa esta fase y desactiva el resto del club (en un solo paso para evitar race)."""
        # Primero activar la nueva, luego desactivar las demás
        self._c.table("ranking_phases").update({"is_active": True}).eq("id", phase_id).execute()
        self._c.table("ranking_phases").update({"is_active": False}).eq(
            "club_id", club_id
        ).neq("id", phase_id).execute()

    def delete_phase(self, phase_id: str, club_id: str) -> None:
        self._c.table("ranking_phases").delete().eq("id", phase_id).eq("club_id", club_id).execute()

    # ================================================================
    # TOURNAMENTS
    # ================================================================

    def list_tournaments(self, club_id: str) -> list[dict]:
        resp = (
            self._c.table("tournaments")
            .select("id, name, start_date, end_date, created_at, updated_at")
            .eq("club_id", club_id)
            .order("created_at", desc=True)
            .execute()
        )
        return resp.data or []

    def get_tournament(self, tournament_id: str, club_id: str) -> Optional[dict]:
        resp = (
            self._c.table("tournaments")
            .select("*")
            .eq("id", tournament_id)
            .eq("club_id", club_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_tournament_public(self, tournament_id: str) -> Optional[dict]:
        """
        Carga un torneo SOLO por su id (sin scope de club) para la vista pública
        compartible. El id es un UUID no adivinable: quien tiene el enlace puede ver
        el torneo en modo lectura. No expone otros clubs ni datos sensibles.
        """
        resp = (
            self._c.table("tournaments")
            .select("id, club_id, name, start_date, end_date, tournament_data")
            .eq("id", tournament_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_latest_tournament(self, club_id: str) -> Optional[dict]:
        """
        Carga el último torneo del club (por updated_at / created_at).
        Útil para restaurar contexto al entrar o cambiar de club.
        """
        resp = (
            self._c.table("tournaments")
            .select("*")
            .eq("club_id", club_id)
            .order("updated_at", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def upsert_tournament(
        self,
        club_id:          str,
        name:             str,
        start_date:       str,
        end_date:         str,
        tournament_data:  dict,
        tournament_id:    Optional[str] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "club_id":          club_id,
            "name":             name,
            "start_date":       start_date,
            "end_date":         end_date,
            "tournament_data":  tournament_data,
        }
        if tournament_id:
            payload["id"] = tournament_id

        resp = self._c.table("tournaments").upsert(payload).execute()
        return resp.data[0]

    def delete_tournament(self, tournament_id: str, club_id: str) -> None:
        self._c.table("tournaments").delete().eq("id", tournament_id).eq("club_id", club_id).execute()
