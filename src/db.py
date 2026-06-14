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

import copy as _copy
import logging
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
# Caché de lecturas frecuentes (TTL corto) para no ir a Supabase en cada rerun.
#
# · El primer parámetro `_db` lleva guion bajo => Streamlit NO lo hashea
#   (sería la propia instancia de SupabaseDB). Se cachea por los args escalares.
# · Las lecturas se devuelven con deepcopy en los métodos públicos para que el
#   código que consuma el resultado pueda ordenarlo/mutarlo sin corromper la caché.
# · La invalidación es CENTRAL: los métodos de escritura (upsert/delete/rename/
#   set_active) llaman a _invalidate_*_cache(), así ningún punto de llamada de la
#   app puede quedar con datos obsoletos tras un guardado.
# · NO se cachea get_tournament: solo se usa en botones (carga puntual) y
#   tournament_from_db muta el dict devuelto.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def _cq_list_phases(_db, club_id):
    return _db._list_phases_impl(club_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cq_get_phase(_db, phase_id, club_id):
    return _db._get_phase_impl(phase_id, club_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cq_list_tournaments(_db, club_id):
    return _db._list_tournaments_impl(club_id)


def _invalidate_phase_cache() -> None:
    try:
        _cq_list_phases.clear()
        _cq_get_phase.clear()
    except Exception:
        pass


def _invalidate_tournament_cache() -> None:
    try:
        _cq_list_tournaments.clear()
    except Exception:
        pass


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
        if resp.data:
            return resp.data[0]
        # return=minimal / RLS: la fila no vuelve en el insert → recuperarla por slug
        return self.get_club_by_slug(slug) or {"name": name, "slug": slug}

    def delete_club(self, club_id: str) -> None:
        self._c.table("clubs").delete().eq("id", club_id).execute()

    # ================================================================
    # USERS
    # ================================================================
    #
    # AISLAMIENTO ENTRE CLUBES (decisión consciente, no deuda):
    # Las escrituras por id (update_user_password, update_user,
    # set_user_active, delete_user) NO filtran por club_id a propósito.
    # El aislamiento aquí lo garantiza el gate superadmin de la página
    # "admin" (app.py), único punto que las invoca. Además, update_user
    # implementa "mover usuario de club", que necesita cambiar club_id;
    # filtrar por club_id chocaría con esa feature. Si en el futuro estas
    # funciones se expusieran fuera del gate superadmin, habría que añadir
    # un filtro por el club_id de destino.

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
        if resp.data:
            return resp.data[0]
        # return=minimal / RLS: recuperar el usuario recién creado por su username
        return self.get_user_by_username(payload["username"]) or dict(payload)

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
        """Lista fases de un club (cacheada, TTL 60s). Copia para mutación segura."""
        return _copy.deepcopy(_cq_list_phases(self, club_id))

    def _list_phases_impl(self, club_id: str) -> list[dict]:
        """Ordena en Python (no en el servidor) para no fallar si la tabla no tiene
        created_at/updated_at en algún entorno — mismo criterio que list_tournaments."""
        resp = (
            self._c.table("ranking_phases")
            .select("id, name, start_date, end_date, is_active, created_at, updated_at")
            .eq("club_id", club_id)
            .execute()
        )
        rows = resp.data or []
        rows.sort(
            key=lambda r: r.get("created_at") or r.get("updated_at") or "",
            reverse=True,
        )
        return rows

    def get_phase(self, phase_id: str, club_id: str) -> Optional[dict]:
        """Carga una fase completa (con todos sus JSONB). Cacheada (TTL 60s)."""
        return _copy.deepcopy(_cq_get_phase(self, phase_id, club_id))

    def _get_phase_impl(self, phase_id: str, club_id: str) -> Optional[dict]:
        resp = (
            self._c.table("ranking_phases")
            .select("*")
            .eq("id", phase_id)
            .eq("club_id", club_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_active_phase(self, club_id: str) -> Optional[dict]:
        """Carga la fase activa de un club (la más reciente con is_active=true).

        Ordena en Python para no depender de created_at en el servidor.
        """
        resp = (
            self._c.table("ranking_phases")
            .select("*")
            .eq("club_id", club_id)
            .eq("is_active", True)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return None
        rows.sort(
            key=lambda r: r.get("created_at") or r.get("updated_at") or "",
            reverse=True,
        )
        return rows[0]

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
            "config_json":     phase_config,
            "groups_json":     groups_data,
            "bookings_json":   bookings_data,
            # matches_json es NOT NULL en algunas instalaciones: nunca enviar None.
            # {} (sin calendario) se lee como "sin schedule_result" en phase_from_db.
            "matches_json":    schedule_result if schedule_result is not None else {},
            "is_active":       True,
        }
        if phase_id:
            payload["id"] = phase_id

        resp = self._c.table("ranking_phases").upsert(payload).execute()
        # Con return=minimal o RLS, resp.data puede venir vacío: no fallar por ello.
        saved = resp.data[0] if resp.data else dict(payload)
        _saved_id = saved.get("id")

        # Desactivar las otras fases del club. Solo si conocemos el id propio
        # (para no desactivar la recién guardada).
        if _saved_id:
            self._c.table("ranking_phases").update({"is_active": False}).eq(
                "club_id", club_id
            ).neq("id", _saved_id).execute()

        _audit_action = "update_phase" if phase_id else "create_phase"
        self.log_audit_event(
            _audit_action,
            club_id=club_id,
            resource="phase",
            resource_id=_saved_id,
            details={"name": name},
        )
        _invalidate_phase_cache()
        return saved

    def set_phase_active(self, phase_id: str, club_id: str) -> None:
        """Activa esta fase y desactiva el resto del club (en un solo paso para evitar race)."""
        # Primero activar la nueva, luego desactivar las demás.
        # El .eq("club_id", club_id) impide activar una fase de otro club.
        self._c.table("ranking_phases").update({"is_active": True}).eq("id", phase_id).eq("club_id", club_id).execute()
        self._c.table("ranking_phases").update({"is_active": False}).eq(
            "club_id", club_id
        ).neq("id", phase_id).execute()
        _invalidate_phase_cache()

    def delete_phase(self, phase_id: str, club_id: str) -> None:
        self._c.table("ranking_phases").delete().eq("id", phase_id).eq("club_id", club_id).execute()
        _invalidate_phase_cache()

    def rename_phase(self, phase_id: str, club_id: str, name: str) -> None:
        """Renombra una fase (solo el nombre, sin tocar el resto de datos)."""
        self._c.table("ranking_phases").update({"name": name}).eq(
            "id", phase_id
        ).eq("club_id", club_id).execute()
        _invalidate_phase_cache()

    # ================================================================
    # TOURNAMENTS
    # ================================================================

    def list_tournaments(self, club_id: str) -> list[dict]:
        """Lista torneos del club (cacheada, TTL 60s). Copia para mutación segura."""
        return _copy.deepcopy(_cq_list_tournaments(self, club_id))

    def _list_tournaments_impl(self, club_id: str) -> list[dict]:
        # select * para no fallar si la tabla no tiene created_at/updated_at,
        # e incluir tournament_data (lo usa la vista «Mis Torneos» para estado).
        resp = (
            self._c.table("tournaments")
            .select("*")
            .eq("club_id", club_id)
            .execute()
        )
        rows = resp.data or []
        rows.sort(
            key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            reverse=True,
        )
        return rows

    def get_tournament(self, tournament_id: str, club_id: str) -> Optional[dict]:
        resp = (
            self._c.table("tournaments")
            .select("*")
            .eq("id", tournament_id)
            .eq("club_id", club_id)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def get_phase_public(self, phase_id: str) -> Optional[dict]:
        """
        Carga una fase SOLO por su id (sin scope de club) para la vista pública.
        El id es un UUID no adivinable: quien tiene el enlace puede ver la
        clasificación en modo lectura. No expone datos sensibles de otros clubs.
        """
        resp = (
            self._c.table("ranking_phases")
            .select("id, club_id, name, start_date, end_date, config_json, groups_json, bookings_json, matches_json")
            .eq("id", phase_id)
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
        rows = self.list_tournaments(club_id)
        return rows[0] if rows else None

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
        _invalidate_tournament_cache()
        # Algunos proyectos no devuelven la fila tras el upsert (RLS / return=minimal).
        # No fallar por ello: devolver lo guardado o el propio payload.
        if resp.data:
            return resp.data[0]
        return payload

    def delete_tournament(self, tournament_id: str, club_id: str) -> None:
        self._c.table("tournaments").delete().eq("id", tournament_id).eq("club_id", club_id).execute()
        _invalidate_tournament_cache()

    # ================================================================
    # TOURNAMENT REGISTRATIONS — inscripciones públicas (insert atómico)
    # ================================================================
    # La tabla `tournament_registrations` permite que la inscripción pública
    # (?join) escriba UNA fila de forma atómica, en vez de re-guardar todo el
    # JSONB del torneo (que causaba lost-update). El admin las "drena" al JSONB.
    #
    # TODOS estos métodos fallan en silencio (None / []) si la tabla aún no
    # existe (SQL sin ejecutar): el llamador hace fallback al flujo antiguo.

    def add_registration(
        self,
        tournament_id: str,
        club_id: Optional[str],
        data: dict,
        registration_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Inserta UNA inscripción de forma atómica. Devuelve la fila, o None si
        la tabla no existe / falla (el llamador hará fallback al JSONB)."""
        payload: dict[str, Any] = {
            "tournament_id": tournament_id,
            "club_id":       club_id or None,
            "data":          data,
            "status":        (data or {}).get("status") or "pending",
        }
        if registration_id:
            payload["id"] = registration_id
        try:
            resp = self._c.table("tournament_registrations").insert(payload).execute()
            return resp.data[0] if resp.data else payload
        except Exception:
            logging.exception("add_registration falló (tournament_id=%s)", tournament_id)
            return None

    def list_registrations(self, tournament_id: str) -> list[dict]:
        """Lista las filas de inscripción de un torneo (ordenadas por created_at).
        Devuelve [] si la tabla no existe / falla."""
        try:
            resp = (
                self._c.table("tournament_registrations")
                .select("*")
                .eq("tournament_id", tournament_id)
                .execute()
            )
            rows = resp.data or []
            rows.sort(key=lambda r: r.get("created_at") or "")
            return rows
        except Exception:
            return []

    def delete_registrations(self, registration_ids: list[str]) -> None:
        """Borra filas de inscripción por id (tras drenarlas al JSONB del torneo)."""
        if not registration_ids:
            return
        try:
            self._c.table("tournament_registrations").delete().in_(
                "id", registration_ids
            ).execute()
        except Exception:
            logging.exception("delete_registrations falló")

    # ================================================================
    # AUDIT LOG
    # ================================================================

    def log_audit_event(
        self,
        action: str,
        club_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Escribe un evento en audit_log. Nunca lanza — fallo silencioso con logging."""
        try:
            self._c.table("audit_log").insert({
                "action":      action,
                "club_id":     club_id,
                "user_id":     user_id,
                "resource":    resource,
                "resource_id": resource_id,
                "details":     details or {},
            }).execute()
        except Exception:
            logging.exception("Error escribiendo en audit_log (action=%s)", action)
