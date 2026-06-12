"""
Vista pública (solo lectura) de la clasificación de una fase de ranking.

No requiere login. Se accede mediante ?r=<phase_id>.
"""
import logging
from html import escape

import streamlit as st

from .db import get_db, is_db_configured
from .db_converters import phase_from_db
from .ranking_scorer import compute_standings, standings_by_group, ScoringRules
from .branding import BRAND_NAME, BRAND_MONOGRAM, BRAND_GRADIENT, public_base_url


_PUBLIC_CSS = f"""
<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="collapsedControl"], .stDeployButton,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}
header[data-testid="stHeader"] {{ display: none !important; }}
.stApp {{ background: #0a1622 !important; }}
.main .block-container {{ max-width: 860px !important; padding-top: 2.5rem !important; }}

.pubr-brand {{ display:flex; align-items:center; gap:.7rem; margin-bottom:1.4rem; }}
.pubr-logo {{
    width:40px; height:40px; border-radius:12px; background:{BRAND_GRADIENT};
    display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; font-size:1.3rem;
    box-shadow:0 6px 22px rgba(0,200,83,.4);
}}
.pubr-brand b {{ color:#eaf6ff; font-size:1.05rem; letter-spacing:-.01em; }}
.pubr-brand span {{ color:#4a7aa0; font-size:.68rem; letter-spacing:.16em; text-transform:uppercase; display:block; }}

.pubr-hero {{
    background:linear-gradient(135deg,#07121f,#0d2b37); border:1px solid rgba(255,255,255,.08);
    border-radius:18px; padding:1.6rem 1.9rem; margin-bottom:1.6rem;
}}
.pubr-hero h1 {{ color:#fff; font-size:1.7rem; font-weight:850; margin:0; letter-spacing:-.02em; }}
.pubr-hero .meta {{ color:#9ec0dc; font-size:.9rem; margin-top:.4rem; }}

.pubr-group {{
    color:#7fffc0; font-size:.75rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
    margin:1.6rem 0 .6rem; padding-bottom:.4rem; border-bottom:1px solid rgba(255,255,255,.08);
}}
.pubr-table {{ width:100%; border-collapse:collapse; margin-bottom:.5rem; }}
.pubr-table th {{
    background:#0b1a2b; color:#9ec0dc; font-size:.72rem; font-weight:700; text-transform:uppercase;
    letter-spacing:.06em; padding:.45rem .6rem; text-align:center; border-bottom:1px solid rgba(255,255,255,.1);
}}
.pubr-table th.left {{ text-align:left; }}
.pubr-table td {{
    padding:.45rem .6rem; font-size:.88rem; color:#cfe2f2; text-align:center;
    border-bottom:1px solid rgba(255,255,255,.04);
}}
.pubr-table td.left {{ text-align:left; }}
.pubr-table tr:hover td {{ background:rgba(255,255,255,.04); }}
.pubr-table td.pts {{ color:#7fffc0; font-weight:800; font-size:.95rem; }}
.medal-1 {{ color:#ffd700; font-size:1rem; }}
.medal-2 {{ color:#c0c0c0; font-size:1rem; }}
.medal-3 {{ color:#cd7f32; font-size:1rem; }}

.pubr-foot {{ text-align:center; color:#3d6a90; font-size:.78rem; margin:2.5rem 0 1rem; }}
.pubr-foot a {{ color:#7fffc0; text-decoration:none; }}
</style>
"""


def render_public_ranking(phase_id: str) -> None:
    """Boundary de error: ante datos inesperados muestra aviso, no un traceback."""
    try:
        _render_public_ranking_impl(phase_id)
    except Exception as _e:
        if type(_e).__name__ in ("StopException", "RerunException"):
            raise
        logging.exception("Error renderizando ranking público")
        try:
            st.error("No se pudo mostrar la clasificación. Comprueba el enlace o reinténtalo.")
        except Exception:
            pass
        st.stop()


def _render_public_ranking_impl(phase_id: str) -> None:
    """Renderiza la clasificación pública de una fase y llama a st.stop()."""
    st.markdown(_PUBLIC_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="pubr-brand"><div class="pubr-logo">{BRAND_MONOGRAM}</div>'
        f'<div><b>{escape(BRAND_NAME)}</b><span>Clasificación en directo</span></div></div>',
        unsafe_allow_html=True,
    )

    if not is_db_configured():
        st.error("Servicio no disponible.")
        st.stop()

    try:
        row = get_db().get_phase_public(phase_id)
    except Exception:
        row = None

    if not row:
        st.markdown(
            '<div class="pubr-hero"><h1>Clasificación no encontrada</h1>'
            '<div class="meta">El enlace no es válido o la fase ya no está disponible.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    try:
        phase, _ = phase_from_db(row)
    except Exception:
        st.error("No se pudo cargar la clasificación.")
        st.stop()

    if phase is None:
        st.error("No se pudo cargar la clasificación.")
        st.stop()

    _dates = f"{phase.start_date} → {phase.end_date}" if phase.end_date else str(phase.start_date)
    st.markdown(
        f'<div class="pubr-hero"><h1>🏅 {escape(phase.name)}</h1>'
        f'<div class="meta">📅 {_dates}</div></div>',
        unsafe_allow_html=True,
    )

    match_results = getattr(phase, "match_results", []) or []
    if not match_results:
        st.info("Aún no hay resultados registrados para esta fase.")
        st.stop()

    rules = getattr(phase, "scoring_rules", None) or ScoringRules()
    pair_names: dict[str, str] = {}
    pair_group: dict[str, str] = {}
    group_label: dict[str, str] = {}
    for g in phase.groups:
        group_label[g.id] = g.name
        for p in g.pairs:
            pair_names[p.id] = p.display_name
            pair_group[p.id] = g.id

    by_group = standings_by_group(match_results, pair_names, rules, pair_group)
    medal_cls = {1: "medal-1", 2: "medal-2", 3: "medal-3"}
    medal_sym = {1: "🥇", 2: "🥈", 3: "🥉"}

    for gid, table in by_group.items():
        g_label = group_label.get(gid, gid)
        st.markdown(f'<div class="pubr-group">{escape(g_label)}</div>', unsafe_allow_html=True)

        rows_html = ""
        for pos, s in enumerate(table, 1):
            mcls = medal_cls.get(pos, "")
            msym = medal_sym.get(pos, str(pos))
            rows_html += (
                f'<tr>'
                f'<td><span class="{mcls}">{msym}</span></td>'
                f'<td class="left">{escape(s.pair_name)}</td>'
                f'<td>{s.played}</td>'
                f'<td>{s.won}</td>'
                f'<td>{s.drawn}</td>'
                f'<td>{s.lost}</td>'
                f'<td>{s.sets_for}-{s.sets_against}</td>'
                f'<td>{s.games_for}-{s.games_against}</td>'
                f'<td>{s.game_diff:+d}</td>'
                f'<td class="pts">{s.points}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<table class="pubr-table">'
            f'<thead><tr>'
            f'<th>#</th><th class="left">Pareja</th>'
            f'<th>PJ</th><th>G</th><th>E</th><th>P</th>'
            f'<th>Sets</th><th>Juegos</th><th>Dif</th><th>Pts</th>'
            f'</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table>',
            unsafe_allow_html=True,
        )

    played_total = sum(1 for r in match_results if r.is_played)
    total = len(match_results)
    st.markdown(
        f'<div style="color:#5a82a4;font-size:.78rem;margin-top:.5rem">'
        f'PJ=Jugados · G=Ganados · E=Empatados · P=Perdidos · Pts=Puntos · '
        f'Desempate: puntos → sets → juegos → cara a cara · '
        f'{played_total}/{total} partidos jugados</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="pubr-foot">Generado con '
        f'<a href="{public_base_url()}">{escape(BRAND_NAME)}</a>'
        f' · Gestión de torneos y rankings deportivos</div>',
        unsafe_allow_html=True,
    )
    st.stop()
