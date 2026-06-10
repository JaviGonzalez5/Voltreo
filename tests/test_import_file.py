"""Tests de la importación flexible Excel/CSV (src/import_file.py)."""
import io

import pandas as pd

from src.import_file import (
    normalize_groups_df, apply_observaciones_to_groups,
    build_template_xlsx, read_groups_file,
)


def _spanish_df():
    return pd.DataFrame([
        {"Grupo": "Nivel 1 — Grupo 1", "Pareja": "García / López",
         "Jugador 1": "Carlos", "Jugador 2": "Marta",
         "Email 1": "c@x.com", "Observaciones": "L X +1930"},
        {"Grupo": "Nivel 1 — Grupo 1", "Pareja": "Ruiz / Sáez",
         "Jugador 1": "Ana", "Jugador 2": "Pedro",
         "Email 1": "", "Observaciones": "PF X2030"},
    ])


class TestNormalize:
    def test_spanish_headers_are_mapped(self):
        out, errs, mapping = normalize_groups_df(_spanish_df())
        assert [e for e in errs if not e.startswith("AVISO")] == []
        for col in ("group_id", "group_name", "pair_name",
                    "player1_name", "player2_name", "observaciones"):
            assert col in out.columns
        assert mapping["Grupo"] == "group_name"
        assert mapping["Jugador 1"] == "player1_name"

    def test_group_id_derived_from_name(self):
        out, _, _ = normalize_groups_df(_spanish_df())
        assert out["group_id"].iloc[0] == out["group_id"].iloc[1]
        assert out["group_id"].iloc[0]  # no vacío

    def test_pair_name_derived_when_missing(self):
        df = pd.DataFrame([{"Grupo": "G1", "Jugador 1": "Ana", "Jugador 2": "Bea"}])
        out, errs, _ = normalize_groups_df(df)
        assert [e for e in errs if not e.startswith("AVISO")] == []
        assert out["pair_name"].iloc[0] == "Ana / Bea"

    def test_unrecognizable_columns_error(self):
        df = pd.DataFrame([{"foo": 1, "bar": 2}])
        _, errs, _ = normalize_groups_df(df)
        assert any("No se reconocen columnas" in e for e in errs)

    def test_empty_rows_dropped_with_warning(self):
        df = _spanish_df()
        df.loc[len(df)] = {c: None for c in df.columns}
        out, errs, _ = normalize_groups_df(df)
        assert len(out) == 2
        assert any(e.startswith("AVISO") for e in errs)


class TestObservaciones:
    def test_availability_applied_to_pairs(self):
        from src.models import Group, Pair, Player
        out, _, _ = normalize_groups_df(_spanish_df())
        gid = out["group_id"].iloc[0]
        groups = [Group.model_construct(id=gid, name="Nivel 1 — Grupo 1", pairs=[
            Pair.model_construct(
                id="p1", name="García / López",
                player_1=Player(name="Carlos"), player_2=Player(name="Marta"),
                group_id=gid, available_weekdays=[], available_from=None,
                available_until=None, availability_notes="", per_day_windows={},
                preferred_weekday=None, preferred_time=None, preferred_slots=[],
                manual_only=False),
            Pair.model_construct(
                id="p2", name="Ruiz / Sáez",
                player_1=Player(name="Ana"), player_2=Player(name="Pedro"),
                group_id=gid, available_weekdays=[], available_from=None,
                available_until=None, availability_notes="", per_day_windows={},
                preferred_weekday=None, preferred_time=None, preferred_slots=[],
                manual_only=False),
        ])]
        n = apply_observaciones_to_groups(groups, out)
        assert n == 2
        p1, p2 = groups[0].pairs
        assert 0 in p1.available_weekdays and 2 in p1.available_weekdays  # L y X
        assert p2.preferred_weekday == 2                                   # PF X2030
        assert p2.preferred_time is not None

    def test_no_observaciones_column_is_noop(self):
        df = pd.DataFrame([{"Grupo": "G", "Jugador 1": "A", "Jugador 2": "B"}])
        out, _, _ = normalize_groups_df(df)
        assert apply_observaciones_to_groups([], out.drop(columns=["observaciones"], errors="ignore")) == 0


class TestTemplateAndRead:
    def test_template_roundtrip(self):
        data = build_template_xlsx()
        buf = io.BytesIO(data)
        buf.name = "plantilla.xlsx"
        df = read_groups_file(buf)
        out, errs, _ = normalize_groups_df(df)
        assert [e for e in errs if not e.startswith("AVISO")] == []
        assert len(out) == 3
