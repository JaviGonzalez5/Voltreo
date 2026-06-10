"""
Importación flexible de grupos/parejas desde Excel (.xlsx/.xls) o CSV.

Pensado para cargar la PRIMERA fase desde el Excel que el club ya tiene
(exportado de Syltek o mantenido a mano), sin exigir el formato exacto del
CSV de ejemplo: las columnas se reconocen por sinónimos habituales en
español y se derivan las que falten (group_id desde el nombre del grupo,
pair_name desde los jugadores).

Columnas canónicas de salida:
  group_id, group_name, pair_name, player1_name, player2_name
  (+ opcionales: player1_email, player1_phone, player2_email, player2_phone,
     observaciones)

La columna "observaciones" (si existe) se interpreta con el mismo parser de
disponibilidad que usa la importación directa de Syltek (días, horarios,
pista fija "PF X2030", "MIRAR MAIL"…).
"""

import io
import re
import unicodedata

import pandas as pd


# ── Sinónimos por columna canónica (se comparan normalizados) ───────────────
_SYNONYMS: dict[str, list[str]] = {
    "group_name":    ["group_name", "grupo", "group", "nombre grupo", "nivel y grupo",
                      "nivel grupo", "nivel/grupo", "categoria", "categoría"],
    "group_id":      ["group_id", "id grupo", "grupo id"],
    "pair_name":     ["pair_name", "pareja", "equipo", "team", "nombre pareja",
                      "nombre equipo", "dupla"],
    "player1_name":  ["player1_name", "jugador1", "jugador 1", "player 1", "player1",
                      "j1", "jugador a", "nombre jugador 1"],
    "player2_name":  ["player2_name", "jugador2", "jugador 2", "player 2", "player2",
                      "j2", "jugador b", "nombre jugador 2"],
    "player1_email": ["player1_email", "email1", "email 1", "correo 1", "correo1",
                      "email jugador 1", "mail 1"],
    "player2_email": ["player2_email", "email2", "email 2", "correo 2", "correo2",
                      "email jugador 2", "mail 2"],
    "player1_phone": ["player1_phone", "telefono1", "telefono 1", "teléfono 1",
                      "tel 1", "movil 1", "móvil 1", "telefono jugador 1"],
    "player2_phone": ["player2_phone", "telefono2", "telefono 2", "teléfono 2",
                      "tel 2", "movil 2", "móvil 2", "telefono jugador 2"],
    "observaciones": ["observaciones", "observacion", "obs", "disponibilidad",
                      "notas", "comentarios", "availability"],
}


def _norm(text: str) -> str:
    """minúsculas, sin acentos, espacios colapsados."""
    raw = str(text or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    out = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[\s_\-\.]+", " ", out).strip()


_LOOKUP = {_norm(v): canon for canon, vs in _SYNONYMS.items() for v in vs}


def read_groups_file(uploaded) -> pd.DataFrame:
    """Lee un fichero subido (csv/xlsx/xls) a DataFrame. Lanza ValueError si no puede."""
    name = str(getattr(uploaded, "name", "")).lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded)
        return pd.read_csv(uploaded)
    except Exception as e:
        raise ValueError(f"No se pudo leer el fichero: {e}") from e


def normalize_groups_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict]:
    """
    Mapea columnas por sinónimos y deriva las que falten.

    Devuelve (df_canónico, errores, mapeo_usado).
    Sin errores ⇒ el df cumple lo que esperan validate_groups_df/_df_to_groups.
    """
    errors: list[str] = []
    mapping: dict[str, str] = {}     # columna original → canónica

    out = pd.DataFrame()
    for col in df.columns:
        canon = _LOOKUP.get(_norm(col))
        if canon and canon not in out.columns:
            out[canon] = df[col]
            mapping[str(col)] = canon

    # ── Derivaciones
    if "group_id" not in out.columns and "group_name" in out.columns:
        out["group_id"] = out["group_name"].map(
            lambda v: re.sub(r"[\s]+", "_", _norm(v)) or "grupo"
        )
    if "pair_name" not in out.columns and {"player1_name", "player2_name"} <= set(out.columns):
        out["pair_name"] = (
            out["player1_name"].fillna("").astype(str).str.strip()
            + " / "
            + out["player2_name"].fillna("").astype(str).str.strip()
        )

    # ── Requisitos mínimos
    required = ["group_name", "group_id", "pair_name", "player1_name", "player2_name"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        cols = ", ".join(str(c) for c in df.columns)
        errors.append(
            "No se reconocen columnas para: "
            + ", ".join(missing)
            + f". Columnas del fichero: {cols}. "
            "Usa cabeceras como Grupo, Pareja, Jugador 1, Jugador 2."
        )
        return out, errors, mapping

    # Filas sin datos esenciales fuera
    before = len(out)
    out = out.dropna(subset=["group_name", "player1_name", "player2_name"])
    out = out[out["group_name"].astype(str).str.strip() != ""]
    dropped = before - len(out)
    if dropped:
        errors.append(f"AVISO: {dropped} fila(s) vacías o incompletas ignoradas.")
    if out.empty:
        errors.append("El fichero no contiene ninguna fila válida de parejas.")
    return out.reset_index(drop=True), errors, mapping


def apply_observaciones_to_groups(groups: list, df: pd.DataFrame) -> int:
    """
    Si el df canónico trae columna 'observaciones', aplica la disponibilidad a
    cada pareja usando el parser de Syltek. Devuelve nº de parejas actualizadas.
    """
    if "observaciones" not in df.columns:
        return 0
    from .syltek_connector import parse_observaciones

    obs_by_key: dict[tuple, str] = {}
    for _, row in df.iterrows():
        key = (str(row["group_id"]).strip(), str(row["pair_name"]).strip())
        txt = "" if pd.isna(row.get("observaciones")) else str(row["observaciones"]).strip()
        if txt:
            obs_by_key[key] = txt

    updated = 0
    for g in groups:
        for pair in g.pairs:
            txt = obs_by_key.get((str(g.id), pair.name))
            if not txt:
                continue
            try:
                av = parse_observaciones(txt)
            except Exception:
                continue
            pair.available_weekdays = av.get("weekdays") or []
            pair.available_from = av.get("available_from")
            pair.available_until = av.get("available_until")
            pair.per_day_windows = av.get("per_day_windows") or {}
            pair.preferred_weekday = av.get("preferred_weekday")
            pair.preferred_time = av.get("preferred_time")
            pair.preferred_slots = av.get("preferred_slots") or []
            pair.manual_only = bool(av.get("manual_only"))
            pair.availability_notes = txt
            updated += 1
    return updated


def build_template_xlsx() -> bytes:
    """Genera un Excel de ejemplo con las cabeceras reconocidas."""
    df = pd.DataFrame([
        {"Grupo": "Nivel 1 — Grupo 1", "Pareja": "García / López",
         "Jugador 1": "Carlos García", "Jugador 2": "Marta López",
         "Email 1": "carlos@email.com", "Email 2": "marta@email.com",
         "Teléfono 1": "600000001", "Teléfono 2": "600000002",
         "Observaciones": "L X +1930"},
        {"Grupo": "Nivel 1 — Grupo 1", "Pareja": "Ruiz / Sáez",
         "Jugador 1": "Ana Ruiz", "Jugador 2": "Pedro Sáez",
         "Email 1": "", "Email 2": "", "Teléfono 1": "", "Teléfono 2": "",
         "Observaciones": "PF X2030"},
        {"Grupo": "Nivel 1 — Grupo 2", "Pareja": "Díaz / Mora",
         "Jugador 1": "Carmen Díaz", "Jugador 2": "Raúl Mora",
         "Email 1": "", "Email 2": "", "Teléfono 1": "", "Teléfono 2": "",
         "Observaciones": ""},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Grupos")
    return buf.getvalue()
