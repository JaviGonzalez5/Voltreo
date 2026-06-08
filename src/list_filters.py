"""
Filtros y búsqueda para las listas principales de la app (torneos, rankings,
clubs, usuarios).

Funciones puras, sin dependencia de Streamlit ni de la base de datos: reciben
listas de dicts (tal como las devuelve `db.py`) y devuelven listas filtradas.
Esto permite testearlas de forma aislada.

Diseño:
  · La búsqueda de texto es por subcadena, sin distinguir mayúsculas ni espacios.
  · Los filtros que no aplican (query vacía, "Todas", etc.) son no-ops y
    devuelven una copia de la lista original.
  · Nunca mutan la lista de entrada.
"""

from typing import Any, Callable, Iterable, Optional


# Centinela: "sin filtro de club" (None es un club_id válido = superadmin sin club)
ALL = "__all__"


def _norm(value: Any) -> str:
    """Normaliza a minúsculas sin espacios sobrantes para comparar."""
    return str(value or "").strip().lower()


def filter_by_text(rows: Iterable[dict], query: str, fields: list[str]) -> list[dict]:
    """
    Filtra `rows` dejando los que contienen `query` (subcadena) en CUALQUIERA
    de los campos indicados. Query vacía => devuelve todos.
    """
    q = _norm(query)
    rows = list(rows)
    if not q:
        return rows
    out = []
    for r in rows:
        for f in fields:
            if q in _norm(r.get(f, "")):
                out.append(r)
                break
    return out


# ---------------------------------------------------------------------------
# Rankings (fases)
# ---------------------------------------------------------------------------

def filter_phases(phases: Iterable[dict], query: str = "", estado: str = "Todas") -> list[dict]:
    """
    Filtra fases de ranking por nombre y estado.

    estado: "Todas" | "Activa" | "Inactiva".
    """
    rows = filter_by_text(phases, query, ["name"])
    if estado == "Activa":
        rows = [p for p in rows if p.get("is_active")]
    elif estado == "Inactiva":
        rows = [p for p in rows if not p.get("is_active")]
    return rows


# ---------------------------------------------------------------------------
# Torneos
# ---------------------------------------------------------------------------

def tournament_divisions(row: dict) -> list[str]:
    """Claves de división de un torneo (ej. ['masculino:1a', 'mixto:3a'])."""
    td = row.get("tournament_data") or {}
    return list(td.get("divisions", []) or [])


def all_division_keys(rows: Iterable[dict]) -> list[str]:
    """Conjunto ordenado de todas las claves de división presentes en los torneos."""
    keys: set[str] = set()
    for r in rows:
        keys.update(tournament_divisions(r))
    return sorted(keys)


def filter_tournaments(
    rows: Iterable[dict],
    query: str = "",
    categories: Optional[list[str]] = None,
    statuses: Optional[list[str]] = None,
    status_of: Optional[Callable[[dict], str]] = None,
) -> list[dict]:
    """
    Filtra torneos por nombre, categorías (claves de división) y estado.

    Args:
        rows:       lista de dicts de torneo (con `tournament_data`).
        query:      búsqueda por nombre (subcadena).
        categories: claves de división a incluir; un torneo pasa si comparte
                    AL MENOS una. Vacío/None = sin filtro.
        statuses:   etiquetas de estado a incluir. Requiere `status_of`.
        status_of:  función que devuelve la etiqueta de estado de un torneo
                    (se inyecta desde la app, que conoce la lógica de estado).
    """
    out = filter_by_text(rows, query, ["name"])

    if categories:
        wanted = set(categories)
        out = [r for r in out if wanted & set(tournament_divisions(r))]

    if statuses and status_of is not None:
        wanted_st = set(statuses)
        out = [r for r in out if status_of(r) in wanted_st]

    return out


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------

def filter_clubs(clubs: Iterable[dict], query: str = "") -> list[dict]:
    """Filtra clubs por nombre o slug."""
    return filter_by_text(clubs, query, ["name", "slug"])


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def filter_users(
    users: Iterable[dict],
    query: str = "",
    role: str = "Todos",
    club_id: Any = ALL,
) -> list[dict]:
    """
    Filtra usuarios por texto (usuario/nombre/email), rol y club.

    Args:
        role:    "Todos" | "club_admin" | "superadmin".
        club_id: ALL = sin filtro; cualquier otro valor (incluido None) filtra
                 por ese club_id exacto.
    """
    rows = filter_by_text(users, query, ["username", "display_name", "email"])
    if role in ("club_admin", "superadmin"):
        rows = [u for u in rows if u.get("role") == role]
    if club_id != ALL:
        rows = [u for u in rows if u.get("club_id") == club_id]
    return rows
