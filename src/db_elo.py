"""
Capa de datos del sistema ELO — DOBLE contexto.

Cada jugador tiene DOS ratings independientes:
  · elo_ranking    — partidos de las fases de ranking del club.
  · elo_tournament — partidos de torneos.

El histórico (elo_history) guarda el contexto de cada partido, de modo que
el historial de ranking y el de torneos se consultan por separado.

Idempotencia: record_match_result NO vuelve a contar un partido cuyo
(source_type, source_id) ya esté en elo_history — re-guardar resultados no
infla el ELO.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from .db import get_db
from .elo_engine import DEFAULT_ELO, EloDelta, compute_match_deltas

log = logging.getLogger(__name__)

# Contextos válidos y su mapeo a columnas
CONTEXTS = ("ranking", "tournament")
_ELO_COL = {"ranking": "elo_ranking", "tournament": "elo_tournament"}
_PLAYED_COL = {"ranking": "matches_played_ranking", "tournament": "matches_played_tournament"}
_WON_COL = {"ranking": "matches_won_ranking", "tournament": "matches_won_tournament"}
_SOURCE_TYPE = {"ranking": "ranking_match", "tournament": "tournament_match"}


def _check_context(context: str) -> None:
    if context not in CONTEXTS:
        raise ValueError(f"context debe ser 'ranking' o 'tournament', no {context!r}")


def _normalize_name_key(name: str) -> str:
    """Clave estable del jugador: minúsculas, sin acentos, espacios colapsados."""
    raw = str(name or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    out = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", out)


def get_or_create_player(
    club_id: str,
    full_name: str,
    email: str = "",
    phone: str = "",
) -> Optional[dict]:
    """Busca el jugador por (club, nombre normalizado); lo crea si no existe."""
    key = _normalize_name_key(full_name)
    if not key:
        return None
    db = get_db()
    resp = (db._c.table("players").select("*")
            .eq("club_id", club_id).eq("name_key", key).execute())
    if resp.data:
        return resp.data[0]
    payload = {
        "club_id": club_id,
        "full_name": str(full_name).strip(),
        "name_key": key,
        "email": email or "",
        "phone": phone or "",
    }
    ins = db._c.table("players").insert(payload).execute()
    if ins.data:
        return ins.data[0]
    # return=minimal: recuperar lo recién insertado
    resp = (db._c.table("players").select("*")
            .eq("club_id", club_id).eq("name_key", key).execute())
    return resp.data[0] if resp.data else None


def get_player_elos(club_id: str, context: str) -> dict[str, int]:
    """{player_id: elo} del contexto pedido, para todo el club."""
    _check_context(context)
    col = _ELO_COL[context]
    db = get_db()
    resp = db._c.table("players").select(f"id, {col}").eq("club_id", club_id).execute()
    return {r["id"]: r.get(col, DEFAULT_ELO) for r in (resp.data or [])}


def get_club_ranking(club_id: str, context: str, limit: int = 200) -> list[dict]:
    """Jugadores del club ordenados por el ELO del contexto (desc)."""
    _check_context(context)
    col = _ELO_COL[context]
    db = get_db()
    resp = (db._c.table("players").select("*")
            .eq("club_id", club_id).order(col, desc=True).limit(limit).execute())
    return resp.data or []


def get_player_by_id(player_id: str) -> Optional[dict]:
    db = get_db()
    resp = db._c.table("players").select("*").eq("id", player_id).execute()
    return resp.data[0] if resp.data else None


def get_player_history(player_id: str, context: str, limit: int = 50) -> list[dict]:
    """Histórico de ELO de un jugador SOLO del contexto pedido."""
    _check_context(context)
    db = get_db()
    resp = (db._c.table("elo_history").select("*")
            .eq("player_id", player_id)
            .eq("source_type", _SOURCE_TYPE[context])
            .order("played_at", desc=True).limit(limit).execute())
    return resp.data or []


def _already_recorded(db, source_type: str, source_id: str) -> bool:
    if not source_id:
        return False
    resp = (db._c.table("elo_history").select("id")
            .eq("source_type", source_type).eq("source_id", source_id)
            .limit(1).execute())
    return bool(resp.data)


def record_match_result(
    club_id: str,
    context: str,                       # 'ranking' | 'tournament'
    source_id: str,                     # match_id — clave de idempotencia
    event_name: str,                    # nombre de la fase o del torneo
    pair_a_player_ids: tuple[str, str],
    pair_a_names: tuple[str, str],
    pair_b_player_ids: tuple[str, str],
    pair_b_names: tuple[str, str],
    winner_pair: str,                   # 'A' | 'B'
    score: str,
) -> list[EloDelta]:
    """
    Actualiza el ELO del CONTEXTO indicado para los 4 jugadores y escribe el
    histórico. Si el partido ya fue contado (mismo source_id), no hace nada.
    """
    _check_context(context)
    source_type = _SOURCE_TYPE[context]
    elo_col, played_col, won_col = _ELO_COL[context], _PLAYED_COL[context], _WON_COL[context]

    db = get_db()
    if _already_recorded(db, source_type, source_id):
        return []   # idempotente: re-guardar no infla el ELO

    all_ids = list(pair_a_player_ids) + list(pair_b_player_ids)
    resp = (db._c.table("players")
            .select(f"id, {elo_col}, {played_col}, {won_col}")
            .in_("id", all_ids).eq("club_id", club_id).execute())
    rows_by_id = {r["id"]: r for r in (resp.data or [])}
    elos_before = {pid: rows_by_id.get(pid, {}).get(elo_col, DEFAULT_ELO)
                   for pid in all_ids}

    deltas = compute_match_deltas(
        pair_a_player_ids, pair_b_player_ids, elos_before, winner_pair,
    )

    a_label = " / ".join(pair_a_names)
    b_label = " / ".join(pair_b_names)

    for d in deltas:
        is_winner = (d.player_id in pair_a_player_ids and winner_pair == "A") or \
                    (d.player_id in pair_b_player_ids and winner_pair == "B")
        existing = rows_by_id.get(d.player_id, {})
        try:
            db._c.table("players").update({
                elo_col: d.elo_after,
                played_col: existing.get(played_col, 0) + 1,
                won_col: existing.get(won_col, 0) + (1 if is_winner else 0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", d.player_id).eq("club_id", club_id).execute()
        except Exception:
            log.exception("Error actualizando ELO (%s) de jugador %s", context, d.player_id)
            continue

        opp_label = b_label if d.player_id in pair_a_player_ids else a_label
        result_label = (f"{'won' if is_winner else 'lost'}: {score}" if score
                        else ("won" if is_winner else "lost"))
        try:
            db._c.table("elo_history").insert({
                "club_id": club_id,
                "player_id": d.player_id,
                "source_type": source_type,
                "source_id": source_id,
                "tournament_name": event_name,
                "elo_before": d.elo_before,
                "elo_after": d.elo_after,
                "delta": d.elo_after - d.elo_before,
                "opponent_names": opp_label,
                "result": result_label,
            }).execute()
        except Exception:
            log.exception("Error escribiendo elo_history de %s", d.player_id)

    return deltas
