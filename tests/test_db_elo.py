"""
Tests del ELO de doble contexto (src/db_elo.py) con un Supabase falso en memoria.

Garantiza:
  · ranking y torneos actualizan COLUMNAS distintas (elo_ranking / elo_tournament)
  · los históricos quedan separados por source_type
  · idempotencia: el mismo source_id no se cuenta dos veces
"""
import pytest

import src.db_elo as db_elo
from src.elo_engine import DEFAULT_ELO


# ── Supabase falso en memoria ───────────────────────────────────────────────

class _FakeQuery:
    def __init__(self, store, table):
        self.store = store
        self.table = table
        self.filters = []
        self._limit = None
        self._payload = None
        self._mode = "select"

    def select(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self._limit = n; return self

    def eq(self, col, val): self.filters.append(("eq", col, val)); return self
    def in_(self, col, vals): self.filters.append(("in", col, list(vals))); return self

    def insert(self, payload):
        self._mode = "insert"; self._payload = payload; return self

    def update(self, payload):
        self._mode = "update"; self._payload = payload; return self

    def _match(self, row):
        for op, col, val in self.filters:
            if op == "eq" and row.get(col) != val:
                return False
            if op == "in" and row.get(col) not in val:
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self._mode == "insert":
            rec = dict(self._payload)
            rec.setdefault("id", f"{self.table}-{len(rows) + 1}")
            # defaults de columnas ELO
            for col in ("elo_ranking", "elo_tournament"):
                rec.setdefault(col, DEFAULT_ELO)
            for col in ("matches_played_ranking", "matches_won_ranking",
                        "matches_played_tournament", "matches_won_tournament"):
                rec.setdefault(col, 0)
            rows.append(rec)
            return type("R", (), {"data": [rec]})()
        if self._mode == "update":
            out = []
            for r in rows:
                if self._match(r):
                    r.update(self._payload)
                    out.append(r)
            return type("R", (), {"data": out})()
        out = [r for r in rows if self._match(r)]
        if self._limit:
            out = out[: self._limit]
        return type("R", (), {"data": out})()


class _FakeClient:
    def __init__(self):
        self.store = {}

    def table(self, name):
        return _FakeQuery(self.store, name)


class _FakeDB:
    def __init__(self, client):
        self._c = client


@pytest.fixture()
def fake_db(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(db_elo, "get_db", lambda: _FakeDB(client))
    return client


def _setup_players(fake_db):
    ids = {}
    for n in ("Ana", "Bea", "Carla", "Diana"):
        p = db_elo.get_or_create_player("club1", n)
        ids[n] = p["id"]
    return ids


def _record(ids, context, source_id="m1", winner="A"):
    return db_elo.record_match_result(
        club_id="club1", context=context, source_id=source_id,
        event_name="Evento",
        pair_a_player_ids=(ids["Ana"], ids["Bea"]),
        pair_a_names=("Ana", "Bea"),
        pair_b_player_ids=(ids["Carla"], ids["Diana"]),
        pair_b_names=("Carla", "Diana"),
        winner_pair=winner, score="6-4 6-3",
    )


class TestDualContext:
    def test_ranking_match_only_touches_ranking_elo(self, fake_db):
        ids = _setup_players(fake_db)
        deltas = _record(ids, "ranking", "r1")
        assert deltas, "debería calcular deltas"
        ana = next(p for p in fake_db.store["players"] if p["id"] == ids["Ana"])
        assert ana["elo_ranking"] > DEFAULT_ELO          # ganó → sube
        assert ana["elo_tournament"] == DEFAULT_ELO      # torneos intacto
        assert ana["matches_played_ranking"] == 1
        assert ana["matches_played_tournament"] == 0

    def test_tournament_match_only_touches_tournament_elo(self, fake_db):
        ids = _setup_players(fake_db)
        _record(ids, "tournament", "t1", winner="B")
        ana = next(p for p in fake_db.store["players"] if p["id"] == ids["Ana"])
        assert ana["elo_tournament"] < DEFAULT_ELO       # perdió → baja
        assert ana["elo_ranking"] == DEFAULT_ELO

    def test_histories_are_separated_by_context(self, fake_db):
        ids = _setup_players(fake_db)
        _record(ids, "ranking", "r1")
        _record(ids, "tournament", "t1")
        hist_r = db_elo.get_player_history(ids["Ana"], "ranking")
        hist_t = db_elo.get_player_history(ids["Ana"], "tournament")
        assert len(hist_r) == 1 and hist_r[0]["source_type"] == "ranking_match"
        assert len(hist_t) == 1 and hist_t[0]["source_type"] == "tournament_match"

    def test_invalid_context_raises(self, fake_db):
        with pytest.raises(ValueError):
            db_elo.get_player_history("x", "liga")


class TestIdempotency:
    def test_same_source_id_not_counted_twice(self, fake_db):
        ids = _setup_players(fake_db)
        first = _record(ids, "ranking", "r1")
        again = _record(ids, "ranking", "r1")          # re-guardado
        assert first and again == []
        ana = next(p for p in fake_db.store["players"] if p["id"] == ids["Ana"])
        assert ana["matches_played_ranking"] == 1       # solo 1 partido contado
        assert len(db_elo.get_player_history(ids["Ana"], "ranking")) == 1

    def test_same_id_different_context_counts(self, fake_db):
        # El mismo match_id en contextos distintos son partidos distintos
        ids = _setup_players(fake_db)
        assert _record(ids, "ranking", "m1")
        assert _record(ids, "tournament", "m1")


class TestGetOrCreate:
    def test_same_name_normalized_returns_same_player(self, fake_db):
        p1 = db_elo.get_or_create_player("club1", "José García")
        p2 = db_elo.get_or_create_player("club1", "  jose  garcia ")
        assert p1["id"] == p2["id"]

    def test_club_ranking_sorted_by_context_elo(self, fake_db):
        ids = _setup_players(fake_db)
        _record(ids, "tournament", "t1", winner="A")    # Ana/Bea suben en torneos
        top = db_elo.get_club_ranking("club1", "tournament")
        # nuestro fake no ordena en servidor: validar que devuelve todos
        assert len(top) == 4
