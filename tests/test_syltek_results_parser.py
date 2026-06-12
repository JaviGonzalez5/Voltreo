"""
Tests del parser de la matriz round-robin de Syltek (resultados + horarios).
Fixture = HTML REAL de /rankings/showtab/101/round5 (Grupo 1), con sus entidades
(&#241;, &nbsp;, &#39;, &amp;) y rarezas (tabs/nbsp finales) tal cual las sirve Syltek.
"""

from src.syltek_connector import parse_round_results, _parse_syltek_datetime


# --- Bloque REAL del Grupo 1 (recortado a span.bold + tabla) ------------------
GRUPO1_HTML = """
<span class="bold">Grupo 1</span><br/><br/>
<form action="" method="get" autocomplete="off" id="list1" name="list1">
<div class="groupBody"><table class="listGrid defaultGrid"><thead><tr>
<th><span class="orderLink"></span></th>
<th class="rankingResultCell"><span>G</span></th>
<th class="rankingResultCell"><span>P</span></th>
<th class="rankingResultCell"><span>E</span></th>
<th class="rankingResultCell"><span>N</span></th>
<th class="rankingResultCell"><span>PT</span></th>
<th class="rankingTeamCell"><span>Equipo</span></th>
<th class="headerTeamCell"><span>J. Ense&#241;at- F. Monroy	</span></th>
<th class="headerTeamCell"><span>C. Angeriz- G. Lendoiro	</span></th>
<th class="headerTeamCell"><span>I. Rey- M. Amado	</span></th>
<th class="headerTeamCell"><span>J. Blanco- M. Varela	</span></th>
<th class="headerTeamCell"><span>I. Rocha- I. Ortiz	</span></th>
<th class="headerTeamCell"><span>J. Lopez- T. A&#241;on	</span></th>
</tr></thead>
<tr class="contentRow defaultRow"><td class="rankingResultCell">1</td><td class="numericCell">2</td><td class="numericCell">1</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">7</td><td class="rankingTeamCell">J. Ense&#241;at- F. Monroy&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGray"></td><td class="rankingMatchCell bgGreen pointer" onclick="document.location = &#39;/admin/index?callback=XXX&amp;type=56&#39;"><a href='/Reservations/show/263662'>6-4 / 1-6 / 6-4</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263308'>5-7 / 5-7</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263865'>0-6 / 6-4 / 6-3</a></td><td class="rankingMatchCell bgGreen pointer"></td><td class="rankingMatchCell bgGreen pointer"></td></tr>
<tr class="contentRow defaultRow"><td class="rankingResultCell">2</td><td class="numericCell">1</td><td class="numericCell">1</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">4</td><td class="rankingTeamCell">C. Angeriz- G. Lendoiro&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263662'>4-6 / 6-1 / 4-6</a></td><td class="rankingMatchCell bgGray"></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263315'>7-6 / 6-3</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263312'>06/07/2026 19:30:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263314'>30/06/2026 19:00:00</a></td><td class="rankingMatchCell bgGreen pointer"></td></tr>
<tr class="contentRow defaultRow"><td class="rankingResultCell">3</td><td class="numericCell">1</td><td class="numericCell">1</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">4</td><td class="rankingTeamCell">I. Rey- M. Amado&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263308'>7-5 / 7-5</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263315'>6-7 / 3-6</a></td><td class="rankingMatchCell bgGray"></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263311'>23/06/2026 19:30:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263316'>07/07/2026 19:00:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263302'>16/06/2026 19:30:00</a></td></tr>
<tr class="contentRow defaultRow"><td class="rankingResultCell">4</td><td class="numericCell">0</td><td class="numericCell">1</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">1</td><td class="rankingTeamCell">J. Blanco- M. Varela&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263865'>6-0 / 4-6 / 3-6</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263312'>06/07/2026 19:30:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263311'>23/06/2026 19:30:00</a></td><td class="rankingMatchCell bgGray"></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263310'>17/06/2026 19:30:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263304'>29/06/2026 21:00:00</a></td></tr>
<tr class="contentRow defaultRow"><td class="rankingResultCell">5</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="rankingTeamCell">I. Rocha- I. Ortiz&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGreen pointer"></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263314'>30/06/2026 19:00:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263316'>07/07/2026 19:00:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263310'>17/06/2026 19:30:00</a></td><td class="rankingMatchCell bgGray"></td><td class="rankingMatchCell bgGreen pointer"></td></tr>
<tr class="contentRow defaultRow"><td class="rankingResultCell">6</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="numericCell">0</td><td class="rankingTeamCell">J. Lopez- T. A&#241;on&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="rankingMatchCell bgGreen pointer"></td><td class="rankingMatchCell bgGreen pointer"></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263302'>16/06/2026 19:30:00</a></td><td class="rankingMatchCell bgGreen pointer"><a href='/Reservations/show/263304'>29/06/2026 21:00:00</a></td><td class="rankingMatchCell bgGreen pointer"></td><td class="rankingMatchCell bgGray"></td></tr>
</table></div></form>
"""


def _by_resid(items):
    return {it["reservation_id"]: it for it in items}


def test_parse_group_label_and_counts():
    groups = parse_round_results(GRUPO1_HTML)
    assert len(groups) == 1
    g = groups[0]
    assert g["group_label"] == "Grupo 1"
    # 4 partidos jugados, 7 programados (deduplicados por id de reserva)
    assert len(g["results"]) == 4
    assert len(g["schedules"]) == 7


def test_results_scores_and_perspective():
    g = parse_round_results(GRUPO1_HTML)[0]
    res = _by_resid(g["results"])

    # Enseñat (fila) vs Angeriz: 6-4 / 1-6 / 6-4 desde la perspectiva de Enseñat
    r = res["263662"]
    assert r["team_a"] == "J. Enseñat- F. Monroy"
    assert r["team_b"] == "C. Angeriz- G. Lendoiro"
    assert r["sets"] == [(6, 4), (1, 6), (6, 4)]

    # Enseñat vs Rey: 5-7 / 5-7 (dos sets)
    assert res["263308"]["sets"] == [(5, 7), (5, 7)]
    assert res["263308"]["team_b"] == "I. Rey- M. Amado"

    # Angeriz vs Rey: 7-6 / 6-3
    assert res["263315"]["sets"] == [(7, 6), (6, 3)]


def test_no_mirror_duplicates():
    g = parse_round_results(GRUPO1_HTML)[0]
    # El mismo id de reserva no debe aparecer dos veces (celdas espejo)
    ids = [r["reservation_id"] for r in g["results"]]
    assert len(ids) == len(set(ids))


def test_schedules_datetime():
    g = parse_round_results(GRUPO1_HTML)[0]
    sch = _by_resid(g["schedules"])
    # Angeriz (fila) vs Blanco programado 06/07/2026 19:30
    s = sch["263312"]
    assert s["team_a"] == "C. Angeriz- G. Lendoiro"
    assert s["team_b"] == "J. Blanco- M. Varela"
    assert s["datetime"] == "2026-07-06 19:30"


def test_played_match_never_in_schedules():
    g = parse_round_results(GRUPO1_HTML)[0]
    res_ids = {r["reservation_id"] for r in g["results"]}
    sch_ids = {s["reservation_id"] for s in g["schedules"]}
    assert res_ids.isdisjoint(sch_ids)


def test_datetime_helper():
    assert _parse_syltek_datetime("06/07/2026 19:30:00") == "2026-07-06 19:30"
    assert _parse_syltek_datetime("1/2/2026 9:05:00") == "2026-02-01 09:05"
    assert _parse_syltek_datetime("sin fecha") == ""
