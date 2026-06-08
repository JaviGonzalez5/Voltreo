"""
Guard de regresión para los nombres de columna de ranking_phases.

Un desajuste entre las columnas que escribe src/db.py y las que existen en la
tabla real de Supabase hace que CADA guardado/carga de ranking falle con
"column not found" (PostgREST). Este test fija el contrato:

  · upsert_phase debe escribir config_json / groups_json / bookings_json / matches_json
  · db_schema.sql debe declarar esas mismas columnas (y no las antiguas)
"""
from pathlib import Path

import pytest

pytest.importorskip("supabase")  # la capa db importa supabase-py
from src.db import SupabaseDB


class _Resp:
    def __init__(self, data=None):
        self.data = data or []


class _Query:
    """Mock encadenable de una query de supabase-py que registra payloads."""
    def __init__(self, table, rec):
        self.table = table
        self.rec = rec
        self._payload = None

    def upsert(self, payload):
        self.rec.setdefault("upsert", {}).setdefault(self.table, []).append(payload)
        self._payload = payload
        return self

    def insert(self, payload):
        self.rec.setdefault("insert", {}).setdefault(self.table, []).append(payload)
        return self

    def update(self, *a, **k): return self
    def delete(self, *a, **k): return self
    def select(self, *a, **k): return self
    def eq(self, *a, **k):  return self
    def neq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self

    def execute(self):
        return _Resp([self._payload] if self._payload else [])


class _FakeClient:
    def __init__(self):
        self.rec = {}

    def table(self, name):
        return _Query(name, self.rec)


def test_upsert_phase_uses_json_column_names():
    client = _FakeClient()
    db = SupabaseDB(client)
    db.upsert_phase(
        club_id="club1", name="Fase", start_date="2026-06-01", end_date="2026-07-01",
        phase_config={"a": 1}, groups_data=[{"g": 1}], bookings_data=[],
        schedule_result=None, phase_id="phase1",
    )
    payloads = client.rec["upsert"]["ranking_phases"]
    assert payloads, "upsert_phase no llamó a upsert sobre ranking_phases"
    keys = set(payloads[0].keys())
    # Columnas reales que el código DEBE usar
    assert {"config_json", "groups_json", "bookings_json", "matches_json"} <= keys
    # Nunca los nombres antiguos (provocaban 'column not found')
    assert not ({"phase_config", "groups_data", "bookings_data", "schedule_result"} & keys)


def test_schema_sql_matches_code_columns():
    schema = (Path(__file__).resolve().parents[1] / "src" / "db_schema.sql").read_text(encoding="utf-8")
    # La definición de la tabla usa los nombres json
    for col in ("config_json", "groups_json", "bookings_json", "matches_json"):
        assert col in schema, f"db_schema.sql no declara la columna {col}"
    # El CREATE TABLE no debe declarar los nombres antiguos (la migración los renombra)
    create_block = schema.split("CREATE TABLE IF NOT EXISTS ranking_phases")[1].split(");")[0]
    for old in ("phase_config", "groups_data", "bookings_data", "schedule_result"):
        assert old not in create_block, f"CREATE TABLE aún usa la columna antigua {old}"
