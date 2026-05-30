from datetime import time

from src.syltek_connector import parse_observaciones


def _has_slot(slots: list[dict], weekday: int, hh: int, mm: int) -> bool:
    for s in slots:
        if s.get("weekday") == weekday and s.get("time") == time(hh, mm):
            return True
    return False


class TestObservacionesMultiPF:

    def test_parse_multiple_pf_slots(self):
        obs = "PF M 19:30; PF J 20:30"
        out = parse_observaciones(obs)

        slots = out.get("preferred_slots", [])
        assert len(slots) == 2
        assert _has_slot(slots, 1, 19, 30)  # Martes
        assert _has_slot(slots, 3, 20, 30)  # Jueves

        # Compatibilidad legacy (primer slot)
        assert out["preferred_weekday"] == 1
        assert out["preferred_time"] == time(19, 30)

    def test_parse_multiple_pf_with_three_letter_days(self):
        obs = "PF MIE 2030; PF VIE 21:00"
        out = parse_observaciones(obs)

        slots = out.get("preferred_slots", [])
        assert len(slots) == 2
        assert _has_slot(slots, 2, 20, 30)  # Miércoles
        assert _has_slot(slots, 4, 21, 0)   # Viernes

    def test_pf_days_added_to_weekdays(self):
        obs = "L-V +1800; PF J 20:30; PF M 19:30"
        out = parse_observaciones(obs)
        weekdays = out.get("weekdays", [])
        assert 1 in weekdays  # martes
        assert 3 in weekdays  # jueves
