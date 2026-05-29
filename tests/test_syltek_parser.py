"""
Tests para _parse_occupied_slots (lectura de reservas de Syltek).

Objetivo principal: DETERMINISMO. El mismo HTML debe producir siempre el
mismo número de reservas, independientemente del orden de las claves JSON.
Cubre el bug: "escaneo dos veces y salen números diferentes".
"""
from datetime import date

from src.syltek_connector import _parse_occupied_slots, _balanced_block


# Fixture: objeto timetable de Syltek con 10 pistas (Padel 1..10) y varias reservas
def _make_html(reservations_js: str) -> str:
    resources = ",".join(
        f"{1476+n}:{{id:'{1476+n}',name:'Padel {n} <br>'}}"
        for n in range(1, 11)
    )
    return f"""
    <html><script>
    var timetable = {{
        resources: {{ {resources} }},
        reservations: {{ {reservations_js} }}
    }};
    </script></html>
    """


def _res(key, y, mo, d, sh, sm, eh, em, court_id):
    return (
        f"{key}:{{"
        f"start: new Date({y},{mo},{d},{sh},{sm},0),"
        f"end: new Date({y},{mo},{d},{eh},{em},0),"
        f"idResource:[{court_id}]"
        f"}}"
    )


class TestDeterminism:

    def test_same_html_same_count(self):
        day = date(2026, 6, 1)
        res = ",".join([
            _res(1, 2026, 5, 1, 18, 0, 19, 30, 1477),
            _res(2, 2026, 5, 1, 20, 0, 21, 30, 1478),
            _res(3, 2026, 5, 1, 19, 0, 20, 30, 1479),
        ])
        html = _make_html(res)
        runs = [len(_parse_occupied_slots(html, day)) for _ in range(5)]
        assert runs == [3, 3, 3, 3, 3], f"No determinista: {runs}"

    def test_key_order_does_not_change_result(self):
        day = date(2026, 6, 1)
        order_a = ",".join([
            _res(1, 2026, 5, 1, 18, 0, 19, 30, 1477),
            _res(2, 2026, 5, 1, 20, 0, 21, 30, 1478),
        ])
        order_b = ",".join([
            _res(2, 2026, 5, 1, 20, 0, 21, 30, 1478),
            _res(1, 2026, 5, 1, 18, 0, 19, 30, 1477),
        ])
        a = _parse_occupied_slots(_make_html(order_a), day)
        b = _parse_occupied_slots(_make_html(order_b), day)
        assert len(a) == len(b) == 2
        # El orden de salida es determinista (ordenado por court+inicio)
        assert [(x.court_id, x.start_datetime) for x in a] == \
               [(x.court_id, x.start_datetime) for x in b]


class TestCompleteness:

    def test_all_ten_courts_read(self):
        day = date(2026, 6, 1)
        res = ",".join([
            _res(n, 2026, 5, 1, 18, 0, 19, 30, 1476 + n)
            for n in range(1, 11)
        ])
        bookings = _parse_occupied_slots(_make_html(res), day)
        assert len(bookings) == 10
        court_ids = {b.court_id for b in bookings}
        assert court_ids == {str(1476 + n) for n in range(1, 11)}

    def test_same_start_different_end_both_kept(self):
        """Dos reservas con mismo inicio en pistas distintas se conservan ambas."""
        day = date(2026, 6, 1)
        res = ",".join([
            _res(1, 2026, 5, 1, 18, 0, 19, 30, 1477),
            _res(2, 2026, 5, 1, 18, 0, 19, 30, 1478),  # mismo inicio, otra pista
        ])
        bookings = _parse_occupied_slots(_make_html(res), day)
        assert len(bookings) == 2

    def test_court_names_resolved(self):
        day = date(2026, 6, 1)
        res = _res(1, 2026, 5, 1, 18, 0, 19, 30, 1480)  # Padel 4
        bookings = _parse_occupied_slots(_make_html(res), day)
        assert bookings[0].court_name == "Padel 4"


class TestEdgeCases:

    def test_no_timetable_returns_empty(self):
        assert _parse_occupied_slots("<html>nada</html>", date(2026, 6, 1)) == []

    def test_no_reservations_returns_empty(self):
        html = _make_html("")
        assert _parse_occupied_slots(html, date(2026, 6, 1)) == []

    def test_multi_court_reservation(self):
        """idResource con varias pistas → una reserva por pista."""
        day = date(2026, 6, 1)
        res = _res(1, 2026, 5, 1, 18, 0, 19, 30, "1477,1478")
        bookings = _parse_occupied_slots(_make_html(res), day)
        assert len(bookings) == 2


class TestBalancedBlock:

    def test_simple(self):
        content, close = _balanced_block("{abc}", 0)
        assert content == "abc"
        assert close == 4

    def test_nested(self):
        text = "{a{b}c}"
        content, close = _balanced_block(text, 0)
        assert content == "a{b}c"

    def test_brace_in_string_ignored(self):
        text = "{name:'a}b'}"
        content, close = _balanced_block(text, 0)
        assert content == "name:'a}b'"
