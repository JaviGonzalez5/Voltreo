"""
Test E2E del flujo de torneo completo (sin Streamlit):
config → estructura → registrar resultados → avance del cuadro →
campeón → serializar a DB → recargar → verificar persistencia.
"""
from datetime import date

from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer, MatchRound,
)
from src.tournament_generator import generate_tournament_structure
from src.tournament_results import (
    register_result, tournament_champion, results_summary,
)
from src.db_converters import tournament_to_db, tournament_from_db


def _pl(n): return TournamentPlayer(name=n, surname="")
def _pr(n): return TournamentPair(name=n, player_1=_pl(f"{n}1"), player_2=_pl(f"{n}2"))


def _bracket(n=8) -> TournamentConfig:
    cfg = TournamentConfig(
        name="Cup", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1),
        format=TournamentFormat.BRACKET, bracket_size=n,
        pairs=[_pr(chr(65 + i)) for i in range(n)],
    )
    return generate_tournament_structure(cfg)


def _m(cfg, rnd, num):
    return next(x for x in cfg.matches if x.round == rnd and x.match_number == num)


class TestTournamentFullFlow:

    def test_full_8_pair_tournament(self):
        cfg = _bracket(8)
        # Cuartos
        for i in range(1, 5):
            qf = _m(cfg, MatchRound.QUARTERFINAL, i)
            register_result(cfg, qf.id, qf.pair_1.id, "6-2 6-2")
        # Semis
        for i in range(1, 3):
            sf = _m(cfg, MatchRound.SEMIFINAL, i)
            assert sf.pair_1 and sf.pair_2, "Semis deben tener ambas parejas tras los cuartos"
            register_result(cfg, sf.id, sf.pair_1.id, "6-3 6-4")
        # Final
        final = _m(cfg, MatchRound.FINAL, 1)
        assert final.pair_1 and final.pair_2
        register_result(cfg, final.id, final.pair_1.id, "7-6 6-4")

        champ = tournament_champion(cfg)
        assert champ is not None
        summ = results_summary(cfg)
        assert summ["champion"] == champ.display_name

    def test_results_survive_db_round_trip(self):
        cfg = _bracket(4)
        for i in (1, 2):
            sf = _m(cfg, MatchRound.SEMIFINAL, i)
            register_result(cfg, sf.id, sf.pair_1.id, "6-0 6-0")
        final = _m(cfg, MatchRound.FINAL, 1)
        register_result(cfg, final.id, final.pair_1.id, "7-5 6-4")
        champ_before = tournament_champion(cfg).display_name

        payload = tournament_to_db(cfg, "club1", cfg.id)
        row = {
            "id": cfg.id, "name": cfg.name,
            "start_date": "2026-06-01", "end_date": "2026-06-01",
            "tournament_data": payload["tournament_data"],
        }
        cfg2 = tournament_from_db(row)

        assert tournament_champion(cfg2).display_name == champ_before
        final2 = _m(cfg2, MatchRound.FINAL, 1)
        assert final2.score == "7-5 6-4"
        assert final2.winner_id is not None

    def test_partial_results_persist(self):
        """Resultados a medias (solo cuartos) sobreviven el round-trip."""
        cfg = _bracket(8)
        qf1 = _m(cfg, MatchRound.QUARTERFINAL, 1)
        register_result(cfg, qf1.id, qf1.pair_1.id, "6-1 6-2")

        payload = tournament_to_db(cfg, "club1", cfg.id)
        row = {
            "id": cfg.id, "name": cfg.name,
            "start_date": "2026-06-01", "end_date": "2026-06-01",
            "tournament_data": payload["tournament_data"],
        }
        cfg2 = tournament_from_db(row)
        # El ganador de QF1 ya está en SF1
        sf1 = _m(cfg2, MatchRound.SEMIFINAL, 1)
        assert sf1.pair_1 is not None
        assert tournament_champion(cfg2) is None  # aún no hay campeón


class TestTournamentMultiTenant:

    def test_two_tournaments_independent(self):
        cfg_a = _bracket(4)
        cfg_b = _bracket(4)
        sf = _m(cfg_a, MatchRound.SEMIFINAL, 1)
        register_result(cfg_a, sf.id, sf.pair_1.id, "6-0 6-0")
        # B no se ve afectado
        assert results_summary(cfg_a)["played"] == 1
        assert results_summary(cfg_b)["played"] == 0

    def test_club_id_in_payload(self):
        cfg = _bracket(4)
        pa = tournament_to_db(cfg, "clubA", None)
        pb = tournament_to_db(cfg, "clubB", None)
        assert pa["club_id"] == "clubA"
        assert pb["club_id"] == "clubB"
