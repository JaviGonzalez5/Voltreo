"""
Ranking Padel Automator — Interfaz Streamlit
"""
import re
import sys
import io
import uuid
from pathlib import Path
from datetime import date, time, datetime, timedelta

import pandas as pd
import streamlit as st

# Raíz del proyecto (resuelve rutas independientemente del cwd del proceso)
_HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# CSS / Tema visual
# ---------------------------------------------------------------------------

_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════
   RANKING PÁDEL AUTOMATOR — Design System v2
   Paleta: Navy #0b1a2b · Verde #00c853 · Gris claro #f5f8fc
   ═══════════════════════════════════════════════════════════════════ */

/* ── BASE ───────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
}
.main .block-container {
    padding-top: 1.6rem;
    padding-bottom: 2.5rem;
    max-width: 1240px;
}

/* ── SIDEBAR base ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #07111d 0%, #0e243d 60%, #132d4a 100%) !important;
    border-right: 1px solid #1a3350 !important;
}
[data-testid="stSidebar"] * { color: #c8dff5 !important; }
[data-testid="stSidebar"] hr { border-color: #1e3a58 !important; margin: .5rem 0 !important; }

/* ── Botones dentro del sidebar ─────────────────────────────────── */
[data-testid="stSidebar"] button {
    background: rgba(255,255,255,.06) !important;
    color: #c8dff5 !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    border-radius: 8px !important;
    font-size: .85rem !important;
    text-align: left !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(0,200,83,.15) !important;
    border-color: rgba(0,200,83,.35) !important;
    color: #90ffc8 !important;
}
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: rgba(0,200,83,.22) !important;
    color: #90ffc8 !important;
    border: 1px solid rgba(0,200,83,.45) !important;
    font-weight: 700 !important;
}
/* ── Expanders del sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,.04) !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    border-radius: 10px !important;
    margin-bottom: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-size: .82rem !important;
    font-weight: 800 !important;
    letter-spacing: .06em !important;
    text-transform: uppercase !important;
    color: #7fa8cc !important;
    padding: 8px 12px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    color: #c8dff5 !important;
}
/* ── Radio dentro sidebar ───────────────────────────────────────── */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px !important; }
[data-testid="stSidebar"] label {
    border-radius: 9px !important;
    padding: 7px 12px !important;
    transition: all .15s !important;
    font-size: .9rem !important;
}
[data-testid="stSidebar"] label:hover { background: rgba(0,200,100,.13) !important; }
[data-testid="stSidebar"] [aria-checked="true"] label {
    background: rgba(0,200,100,.2) !important;
    color: #90ffc8 !important;
    font-weight: 700 !important;
}

/* ── CABECERA DE PÁGINA ─────────────────────────────────────────── */
.pp-page-title {
    display: flex;
    align-items: center;
    gap: .7rem;
    padding: .5rem 0 1rem 0;
    border-bottom: 3px solid #00c853;
    margin-bottom: 1.8rem;
}
.pp-page-title .pp-icon { font-size: 2.1rem; line-height: 1; }
.pp-page-title .pp-text h1 {
    margin: 0;
    font-size: 1.8rem;
    font-weight: 800;
    color: #07111d;
    line-height: 1.1;
    letter-spacing: -.02em;
}
.pp-page-title .pp-text p {
    margin: .25rem 0 0 0;
    font-size: .88rem;
    color: #6b82a0;
}

/* ── SECCIÓN CON TÍTULO ─────────────────────────────────────────── */
.pp-section {
    background: #fff;
    border: 1px solid #e4edf8;
    border-radius: 16px;
    padding: 1.4rem 1.6rem 1.2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 6px rgba(11,26,43,.06), 0 4px 16px rgba(11,26,43,.04);
}
.pp-section-title {
    display: flex;
    align-items: center;
    gap: .45rem;
    font-size: .72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: #8faac8;
    margin-bottom: 1rem;
    padding-bottom: .6rem;
    border-bottom: 1px solid #eef3fa;
}
.pp-section-title span { font-size: 1rem; }

/* ── MÉTRICAS ────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #fff !important;
    border: 1px solid #e4edf8 !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 6px rgba(11,26,43,.06) !important;
    transition: box-shadow .15s !important;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 14px rgba(11,26,43,.10) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 800 !important;
    color: #07111d !important;
    letter-spacing: -.02em !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: .72rem !important;
    color: #8faac8 !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
}

/* ── BOTONES ─────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: .9rem !important;
    letter-spacing: .01em !important;
    transition: all .2s ease !important;
    padding: .45rem 1.2rem !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00d45a 0%, #00a86b 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 3px 12px rgba(0,200,83,.30) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 20px rgba(0,200,83,.42) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0) !important; }
.stButton > button[kind="secondary"] {
    border: 1.5px solid #c8dfee !important;
    color: #1b3a58 !important;
    background: #fff !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #00c853 !important;
    color: #007a38 !important;
    background: rgba(0,200,83,.05) !important;
    transform: translateY(-1px) !important;
}
/* Botón de descarga */
[data-testid="stDownloadButton"] button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #1565c0, #0d47a1) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 3px 10px rgba(21,101,192,.3) !important;
}
[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(21,101,192,.4) !important;
}

/* ── TABS ───────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    gap: 2px;
    border-bottom: 2px solid #e4edf8;
    background: #f5f8fc;
    border-radius: 10px 10px 0 0;
    padding: 4px 4px 0;
}
[data-testid="stTabs"] button[role="tab"] {
    border-radius: 8px 8px 0 0 !important;
    padding: 9px 20px !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
    color: #7f9ab5 !important;
    background: transparent !important;
    border: none !important;
    transition: all .15s !important;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: #1b3a58 !important; }
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #007a38 !important;
    background: #fff !important;
    border-bottom: 3px solid #00c853 !important;
    font-weight: 700 !important;
}

/* ── EXPANDERS ──────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #e4edf8 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 4px rgba(11,26,43,.05) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #1b3a58 !important;
    font-size: .92rem !important;
    padding: .7rem 1rem !important;
}
[data-testid="stExpander"] summary:hover { background: #f5f8fc !important; }

/* ── ALERTS ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border-width: 1px !important;
    font-size: .9rem !important;
}

/* ── DATAFRAMES ─────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 6px rgba(11,26,43,.07) !important;
    border: 1px solid #e4edf8 !important;
}

/* ── INPUTS / SLIDERS ───────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 9px !important;
    border-color: #d0e0f0 !important;
    font-size: .92rem !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #00c853 !important;
    box-shadow: 0 0 0 2px rgba(0,200,83,.15) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #00c853 !important;
    border-color: #00c853 !important;
}

/* ── PROGRESS ───────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #00d45a, #00897b) !important;
    border-radius: 6px !important;
}

/* ── FILE UPLOADER ──────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border-radius: 12px !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #c0d8f0 !important;
    border-radius: 12px !important;
    background: #f5f8fc !important;
    transition: all .2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #00c853 !important;
    background: rgba(0,200,83,.04) !important;
}

/* ── TOGGLES / CHECKBOXES ───────────────────────────────────────── */
[data-testid="stCheckbox"] label,
[data-testid="stToggle"] label {
    font-size: .92rem !important;
    color: #2c3e50 !important;
}

/* ── SIDEBAR STEPPER ────────────────────────────────────────────── */
.pp-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 10px;
    border-radius: 9px;
    margin: 2px 0;
    font-size: .84rem;
    transition: background .15s;
}
.pp-step.done   { color: #7fffc0 !important; }
.pp-step.active { color: #fff !important; font-weight: 700; background: rgba(0,200,83,.18); }
.pp-step.todo   { color: #4a6a8a !important; }
.pp-step .pp-step-dot {
    width: 22px; height: 22px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .75rem; flex-shrink: 0; font-weight: 700;
}
.pp-step.done .pp-step-dot   { background: #00c853; color: #fff; }
.pp-step.active .pp-step-dot { background: #fff; color: #07111d; }
.pp-step.todo .pp-step-dot   { background: #1e3a58; color: #4a6a8a; }

/* ── BADGES ─────────────────────────────────────────────────────── */
.pp-badge-safe {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0,200,83,.15);
    color: #7fffc0 !important;
    border: 1px solid rgba(0,200,83,.25);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: .78rem; font-weight: 700;
}
.pp-badge-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(244,67,54,.18);
    color: #ff8a80 !important;
    border: 1px solid rgba(244,67,54,.28);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: .78rem; font-weight: 700;
}

/* ── TORNEOS — Tarjeta TOP ──────────────────────────────────────── */
.t-top-banner {
    background: linear-gradient(135deg, #1a0533 0%, #3b0f6e 40%, #6a1b9a 100%);
    border: 2px solid #ffd700;
    border-radius: 20px;
    padding: 1.4rem 2rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 4px 24px rgba(106,27,154,.35), 0 0 0 1px rgba(255,215,0,.15);
    position: relative;
    overflow: hidden;
}
.t-top-banner::before {
    content: "★ TOP";
    position: absolute;
    top: 12px; right: 20px;
    font-size: .75rem; font-weight: 900;
    color: #ffd700;
    letter-spacing: .15em;
    text-shadow: 0 0 10px rgba(255,215,0,.6);
}
.t-top-banner .t-top-name {
    font-size: 1.6rem;
    font-weight: 900;
    color: #fff;
    letter-spacing: -.01em;
    margin-bottom: .2rem;
}
.t-top-banner .t-top-meta {
    font-size: .88rem;
    color: rgba(255,255,255,.75);
}
.t-top-banner .t-top-prize {
    font-size: 1rem;
    font-weight: 700;
    color: #ffd700;
    margin-top: .5rem;
}
/* Badge de categoría */
.t-cat-masc  { background:#1565c0; color:#fff; padding:3px 12px; border-radius:20px; font-size:.78rem; font-weight:700; display:inline-block; }
.t-cat-fem   { background:#c2185b; color:#fff; padding:3px 12px; border-radius:20px; font-size:.78rem; font-weight:700; display:inline-block; }
.t-cat-mix   { background:#6a1b9a; color:#fff; padding:3px 12px; border-radius:20px; font-size:.78rem; font-weight:700; display:inline-block; }
.t-subcat    { background:#263238; color:#90caf9; border:1px solid #37474f; padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:700; display:inline-block; margin-left:6px; }
/* Tarjeta torneo normal */
.t-card {
    background: #fff;
    border: 1.5px solid #e4edf8;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    margin-bottom: .9rem;
    box-shadow: 0 1px 8px rgba(11,26,43,.07);
    transition: box-shadow .15s, transform .15s;
}
.t-card:hover { box-shadow: 0 4px 18px rgba(11,26,43,.12); transform: translateY(-1px); }
.t-card-name { font-size: 1.05rem; font-weight: 800; color: #07111d; }
.t-card-meta { font-size: .82rem; color: #6b82a0; margin-top: .2rem; }

/* ── ESTADO VACÍO ───────────────────────────────────────────────── */
.pp-empty {
    text-align: center;
    padding: 3.5rem 1.5rem;
    background: #f5f8fc;
    border-radius: 16px;
    border: 2px dashed #d0e0f0;
    margin: 1rem 0;
}
.pp-empty .pp-empty-icon { font-size: 3.2rem; margin-bottom: .6rem; }
.pp-empty .pp-empty-title {
    font-size: 1.15rem; font-weight: 700;
    color: #1b3a58; margin-bottom: .4rem;
}
.pp-empty .pp-empty-text { font-size: .9rem; color: #7f9ab5; }

/* ── STAT CHIPS (resumen rápido) ────────────────────────────────── */
.pp-chips { display: flex; flex-wrap: wrap; gap: .5rem; margin: .8rem 0; }
.pp-chip {
    display: inline-flex; align-items: center; gap: .3rem;
    background: #f0f6ff;
    border: 1px solid #dce8f8;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: .82rem; font-weight: 600; color: #1b3a58;
}
.pp-chip.green  { background:#e8faf0; border-color:#a8e6c0; color:#005a29; }
.pp-chip.red    { background:#fef0f0; border-color:#f5c0c0; color:#8b0000; }
.pp-chip.orange { background:#fff5e8; border-color:#f5d9a8; color:#7a4000; }

/* ── CÓDIGO / FORMATO CSV ───────────────────────────────────────── */
[data-testid="stCode"] {
    border-radius: 10px !important;
    font-size: .82rem !important;
}

/* ── SPINNER ────────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {
    border-color: #00c853 !important;
    border-right-color: transparent !important;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _section_start(icon: str, title: str) -> None:
    """Inicia un bloque visual con título de sección."""
    st.markdown(
        f'<div class="pp-section-title"><span>{icon}</span>{title}</div>',
        unsafe_allow_html=True,
    )


def _stat_chips(*chips: tuple[str, str, str]) -> None:
    """Muestra chips de estadísticas inline. Cada chip: (texto, color, icono)."""
    parts = "".join(
        f'<span class="pp-chip {color}">{icon} {text}</span>'
        for text, color, icon in chips
    )
    st.markdown(f'<div class="pp-chips">{parts}</div>', unsafe_allow_html=True)


def _empty_state(icon: str, title: str, text: str) -> None:
    """Muestra un estado vacío con diseño visual."""
    st.markdown(
        f'<div class="pp-empty">'
        f'<div class="pp-empty-icon">{icon}</div>'
        f'<div class="pp-empty-title">{title}</div>'
        f'<div class="pp-empty-text">{text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _page_header(icon: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="pp-page-title">'
        f'<div class="pp-icon">{icon}</div>'
        f'<div class="pp-text"><h1>{title}</h1>'
        f'{"<p>" + subtitle + "</p>" if subtitle else ""}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _sidebar_step(label: str, state: str, num: int) -> None:
    """state: 'done' | 'active' | 'todo'"""
    dot = "✓" if state == "done" else str(num)
    st.sidebar.markdown(
        f'<div class="pp-step {state}">'
        f'<span class="pp-step-dot">{dot}</span>{label}</div>',
        unsafe_allow_html=True,
    )


def _step_header(num: int, title: str) -> None:
    """Cabecera numerada de paso en una página (ej. página Syltek)."""
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.8rem">'
        f'<span style="background:#00c853;color:#fff;border-radius:50%;width:28px;height:28px;'
        f'display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;flex-shrink:0">'
        f'{num}</span>'
        f'<span style="font-size:1.1rem;font-weight:700;color:#0b1a2b">{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# Aseguramos que src/ esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings
from src.models import (
    Player, Pair, Group, Court, Booking, RankingPhase,
    Match, MatchStatus, ScheduleResult,
)
from src.ranking_generator import generate_all_matches
from src.scheduler import Scheduler
from src.excel_exporter import export_to_excel
from src.message_generator import generate_all_group_messages, generate_all_pair_messages
from src.validators import (
    validate_groups_df, validate_bookings_df, validate_phase_dates,
    validate_groups, issues_summary,
)
from src.schedule_validator import validate_schedule, validation_summary, SEVERITY_EMOJI
from src.excel_template_exporter import export_groups_to_template
from src.scheduler import balance_metrics, pairs_with_most_conflicts
from src.syltek_connector import SyltekConnector, run_login_check, _parse_occupied_slots
from src.tournament_models import (
    TournamentConfig, TournamentFormat, TournamentPair, TournamentPlayer,
    TournamentCourt, TMatchStatus, MatchRound,
    TournamentCategory, TournamentSubcategory,
)
from src.tournament_generator import (
    generate_tournament_structure, tournament_summary as _t_summary,
)
from src.tournament_scheduler import schedule_tournament, tournament_schedule_summary
from src.db import get_db, is_db_configured
from src.auth import (
    render_login_screen, is_authenticated, get_session_user,
    is_superadmin, current_club_id, current_club_name, logout,
)
from src.db_converters import (
    phase_to_db, schedule_result_to_db, phase_from_db,
    tournament_to_db, tournament_from_db,
)


# ---------------------------------------------------------------------------
# Helpers de conversión CSV → modelos (deben definirse antes del routing)
# ---------------------------------------------------------------------------

def _mc(cls, **kw):
    """model_construct con uuid por defecto para el campo id."""
    from uuid import uuid4
    if "id" not in kw and hasattr(cls.model_fields, "__contains__") and "id" in cls.model_fields:
        kw["id"] = str(uuid4())
    return cls.model_construct(**kw)


def _build_calendar_html(matches: list, week_start: "date") -> str:
    """Genera una tabla HTML estilo calendario semanal con los partidos."""
    from collections import defaultdict
    from datetime import timedelta as _td

    week_dates = [week_start + _td(days=i) for i in range(7)]
    day_names_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

    # Partidos de la semana
    week_matches = [
        m for m in matches
        if m.suggested_date and m.suggested_date in week_dates
    ]

    # Franjas horarias únicas (ordenadas)
    times = sorted({m.suggested_start_time for m in week_matches if m.suggested_start_time})

    if not times:
        return "<p style='color:#888;padding:12px'>No hay partidos programados esta semana.</p>"

    # Agrupar por (fecha, hora)
    cell: dict = defaultdict(list)
    for m in week_matches:
        if m.suggested_start_time:
            cell[(m.suggested_date, m.suggested_start_time)].append(m)

    # Colores por grupo (paleta cíclica)
    group_colors = [
        "#1976d2", "#388e3c", "#f57c00", "#7b1fa2", "#c62828",
        "#00838f", "#6d4c41", "#1565c0", "#2e7d32", "#ad1457",
    ]
    group_ids = list(dict.fromkeys(m.group_id for m in week_matches))
    group_color_map = {gid: group_colors[i % len(group_colors)] for i, gid in enumerate(group_ids)}

    css = """
<style>
.ppcal{border-collapse:collapse;width:100%;font-family:'Inter','Segoe UI',sans-serif;font-size:12px;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)}
.ppcal th{background:linear-gradient(135deg,#0b1a2b,#132d4a);color:#dce8f5;padding:10px 6px;text-align:center;border:1px solid #1f3a58;white-space:nowrap}
.ppcal td{padding:4px;border:1px solid #e8f0fa;vertical-align:top;background:#fafcff;min-width:110px}
.ppcal .time-col{background:#f0f5ff;font-weight:700;text-align:center;color:#0b1a2b;font-size:13px;padding:8px;white-space:nowrap;width:52px;border-right:2px solid #e0eaf5}
.ppcal .has-match{background:#fff}
.pp-cal-card{border-radius:7px;padding:6px 8px;margin:3px 0;border-left:4px solid #1976d2;background:#edf4fd;line-height:1.4;transition:box-shadow .15s}
.pp-cal-card:hover{box-shadow:0 2px 8px rgba(0,0,0,.12)}
.pp-cal-card.conflict{background:#fde8e8;border-left-color:#d32f2f}
.pp-vs{font-weight:700;font-size:11px;color:#0b1a2b}
.pp-info{font-size:10px;color:#7f9ab5;margin-top:2px}
.pp-court{font-size:10px;font-weight:700;color:#00874a}
.day-name{font-size:13px;font-weight:800;color:#fff}
.day-date{font-size:10px;opacity:.7;margin-top:2px;color:#b0cce0}
.today-hdr{background:linear-gradient(135deg,#006633,#00a854) !important}
</style>"""

    today = date.today()

    # Cabecera
    rows = [css, '<table class="ppcal"><thead><tr>',
            '<th style="width:52px">Hora</th>']
    for i, d in enumerate(week_dates):
        cnt = sum(len(cell[(d, t)]) for t in times)
        extra = ' class="today-hdr"' if d == today else ""
        rows.append(
            f'<th{extra}>'
            f'<div class="day-name">{day_names_es[i]}</div>'
            f'<div class="day-date">{d.strftime("%d/%m")}</div>'
            f'{"<br><small style=\'opacity:.7\'>(" + str(cnt) + ")</small>" if cnt else ""}'
            f'</th>'
        )
    rows.append("</tr></thead><tbody>")

    # Filas por franja horaria
    for t in times:
        rows.append(f'<tr><td class="time-col">{t.strftime("%H:%M")}</td>')
        for d in week_dates:
            ms = cell.get((d, t), [])
            if ms:
                rows.append('<td class="has-match">')
                for m in ms:
                    color = group_color_map.get(m.group_id, "#1976d2")
                    is_conf = m.status == MatchStatus.CONFLICT
                    card_cls = "pp-cal-card conflict" if is_conf else "pp-cal-card"
                    border_color = "#d32f2f" if is_conf else color
                    bg_color = "#fde8e8" if is_conf else "#e8f4fd"
                    court_txt = m.court.name if m.court else "—"
                    p1 = m.pair_1.display_name
                    p2 = m.pair_2.display_name
                    rows.append(
                        f'<div class="{card_cls}" style="border-left-color:{border_color};background:{bg_color}">'
                        f'<div class="pp-vs">{p1}</div>'
                        f'<div class="pp-vs" style="color:#555">vs {p2}</div>'
                        f'<div class="pp-info"><span class="pp-court">{court_txt}</span>'
                        f' · <span style="color:{color}">{m.group_name}</span></div>'
                        f'</div>'
                    )
                rows.append("</td>")
            else:
                rows.append("<td></td>")
        rows.append("</tr>")

    rows.append("</tbody></table>")
    return "\n".join(rows)


def _df_to_groups(df: pd.DataFrame) -> list[Group]:
    """Convierte un DataFrame de grupos al modelo Group."""
    groups_dict: dict[str, Group] = {}
    for _, row in df.iterrows():
        gid = str(row["group_id"]).strip()
        gname = str(row["group_name"]).strip()
        if gid not in groups_dict:
            groups_dict[gid] = Group.model_construct(id=gid, name=gname, pairs=[])
        p1 = Player.model_construct(
            id=str(uuid.uuid4()),
            name=str(row["player1_name"]).strip(),
            surname="",
            email=str(row.get("player1_email", "")).strip() or None,
            phone=str(row.get("player1_phone", "")).strip() or None,
        )
        p2 = Player.model_construct(
            id=str(uuid.uuid4()),
            name=str(row["player2_name"]).strip(),
            surname="",
            email=str(row.get("player2_email", "")).strip() or None,
            phone=str(row.get("player2_phone", "")).strip() or None,
        )
        pair = Pair.model_construct(
            id=str(uuid.uuid4()),
            name=str(row["pair_name"]).strip(),
            player_1=p1,
            player_2=p2,
            group_id=gid,
            available_weekdays=[],
            available_from=None,
            available_until=None,
            availability_notes="",
            per_day_windows={},
            preferred_weekday=None,
            preferred_time=None,
            manual_only=False,
        )
        groups_dict[gid].pairs.append(pair)
    return list(groups_dict.values())


def _df_to_bookings(df: pd.DataFrame) -> list[Booking]:
    """Convierte un DataFrame de reservas al modelo Booking."""
    bookings = []
    for _, row in df.iterrows():
        bookings.append(Booking.model_construct(
            id=str(uuid.uuid4()),
            court_id=str(row["court_id"]).strip(),
            court_name=str(row["court_name"]).strip(),
            start_datetime=pd.to_datetime(row["start_datetime"]).to_pydatetime(),
            end_datetime=pd.to_datetime(row["end_datetime"]).to_pydatetime(),
            description=str(row.get("description", "")).strip(),
            source=str(row.get("source", "manual")).strip(),
        ))
    return bookings


# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ranking Pádel Automator",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Estado de sesión (persistencia entre páginas)
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "groups": [],
        "courts": [],
        "bookings": [],
        "matches": [],
        "schedule_result": None,
        "phase": None,
        "dry_run": True,
        "data_loaded": False,
        "matches_generated": False,
        "matches_scheduled": False,
        # Módulo de torneos
        "tournament": None,
        # Navegación
        "_nav_page": "club_config",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
_inject_css()

# ---------------------------------------------------------------------------
# Base de datos y autenticación
# ---------------------------------------------------------------------------

_db_ok = is_db_configured()
_db = get_db() if _db_ok else None

if _db_ok:
    if not is_authenticated():
        render_login_screen(_db)   # calls st.stop() internally
    else:
        # Cargar fase activa del club si aún no hay datos en sesión
        _cid_load = current_club_id()
        if _cid_load and _db is not None and st.session_state.phase is None and not st.session_state.get("_db_phase_loaded"):
            st.session_state["_db_phase_loaded"] = True
            try:
                _row = _db.get_active_phase(_cid_load)
                if _row:
                    _loaded_phase, _loaded_result = phase_from_db(_row)
                    st.session_state.phase = _loaded_phase
                    st.session_state["db_phase_id"] = _row["id"]
                    if _loaded_phase.groups:
                        st.session_state.groups = list(_loaded_phase.groups)
                        st.session_state.data_loaded = True
                    if _loaded_phase.bookings:
                        st.session_state.bookings = list(_loaded_phase.bookings)
                    if _loaded_result:
                        st.session_state.schedule_result = _loaded_result
                        st.session_state.matches_scheduled = True
                        st.session_state.matches = _loaded_result.scheduled + _loaded_result.conflicts
                        st.session_state.matches_generated = True
            except Exception:
                pass  # BD no disponible o fase inválida — ignorar silenciosamente

# ---------------------------------------------------------------------------
# Sidebar — navegación
# ---------------------------------------------------------------------------

st.sidebar.markdown(
    '<div style="text-align:center;padding:1rem 0 .5rem 0">'
    '<span style="font-size:2.2rem">🎾</span>'
    '<div style="font-size:1.15rem;font-weight:800;color:#fff;letter-spacing:.02em;margin-top:.3rem">Ranking Pádel</div>'
    '<div style="font-size:.72rem;color:#7fa8cc;letter-spacing:.08em;text-transform:uppercase">Automator</div>'
    '</div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown('<hr style="border-color:#2a4a6b;margin:.6rem 0">', unsafe_allow_html=True)

# ── Página actual ─────────────────────────────────────────────────────────
_s = st.session_state
page = _s.get("_nav_page", "club_config")

# ── Usuario y club ─────────────────────────────────────────────────────────
_club_name_sidebar = ""
if _db_ok and is_authenticated():
    _user = get_session_user()

    if is_superadmin() and _db is not None:
        _clubs = _db.list_clubs()
        if _clubs:
            _club_options = {c["name"]: c["id"] for c in _clubs}
            _prev = st.session_state.get("superadmin_selected_club_id")
            _default_idx = list(_club_options.values()).index(_prev) if _prev in _club_options.values() else 0
            _sel_name = st.sidebar.selectbox(
                "🏢 Club activo", options=list(_club_options.keys()),
                index=_default_idx, key="superadmin_club_select",
            )
            st.session_state["superadmin_selected_club_id"]   = _club_options[_sel_name]
            st.session_state["superadmin_selected_club_name"] = _sel_name
            _club_name_sidebar = _sel_name
        else:
            st.sidebar.warning("⚠️ No hay clubs. Crea uno en Administración.")
    else:
        _club_name_sidebar = current_club_name()
        if _club_name_sidebar:
            st.sidebar.markdown(
                f'<div style="padding:4px 10px 2px;font-size:.8rem">'
                f'🏢 <b>{_club_name_sidebar}</b></div>',
                unsafe_allow_html=True,
            )

    st.sidebar.markdown(
        f'<div style="padding:2px 10px 6px;font-size:.78rem;opacity:.75">'
        f'👤 {_user["display_name"]}</div>',
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True, key="btn_logout"):
        logout()

st.sidebar.markdown('<hr style="border-color:#1e3a58;margin:.5rem 0">', unsafe_allow_html=True)

# ── Función de navegación ──────────────────────────────────────────────────
def _nav(key: str, label: str, done: bool = False, active: bool = False, hint: str = "") -> None:
    _icon = "✅" if done else ("▶️" if active else "   "  )
    if st.sidebar.button(
        f"{_icon} {label}", key=f"nav_{key}",
        use_container_width=True,
        type="primary" if active else "secondary",
    ):
        st.session_state["_nav_page"] = key
        st.rerun()
    if active and hint:
        st.sidebar.markdown(
            f'<div style="font-size:.73rem;color:#5a8cb0;padding:1px 4px 6px 14px">'
            f'💡 {hint}</div>',
            unsafe_allow_html=True,
        )

def _section_label(txt: str) -> None:
    st.sidebar.markdown(
        f'<div style="font-size:.68rem;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:#3d6080;padding:8px 10px 4px">{txt}</div>',
        unsafe_allow_html=True,
    )

# ── CLUB ───────────────────────────────────────────────────────────────────
_section_label("🏢 Club")
_nav("club_config", "Configuración del club",
     done=bool(_club_name_sidebar), active=(page == "club_config"),
     hint="Nombre, pistas, horarios y contacto")

st.sidebar.markdown('<hr style="border-color:#1e3a58;margin:.5rem 0">', unsafe_allow_html=True)

# ── RANKING ────────────────────────────────────────────────────────────────
_R_STEPS = [
    ("config",   "Configurar fase",    "Define fechas, pistas y parámetros",  _s.phase is not None),
    ("import",   "Importar datos",     "Sube grupos, parejas y reservas",      _s.data_loaded),
    ("generate", "Generar calendario", "Crea los partidos automáticamente",    _s.matches_generated),
    ("export",   "Exportar",           "Excel, mensajes WhatsApp y más",       _s.matches_scheduled),
    ("review",   "Revisión",           "Comprueba conflictos y ajustes",       _s.matches_scheduled),
    ("syltek",   "Publicar en Syltek", "Reserva pistas automáticamente",       False),
]
_IS_RANKING = page in {s[0] for s in _R_STEPS}

_section_label("📊 Ranking")
with st.sidebar.expander("Ver pasos del ranking →", expanded=_IS_RANKING):
    for _sk, _sl, _sh, _sd in _R_STEPS:
        _nav(_sk, f"{'1234567890'[_R_STEPS.index((_sk,_sl,_sh,_sd))]}. {_sl}",
             done=_sd, active=(page==_sk), hint=_sh)

st.sidebar.markdown('<hr style="border-color:#1e3a58;margin:.5rem 0">', unsafe_allow_html=True)

# ── TORNEOS ────────────────────────────────────────────────────────────────
_T_OBJ = _s.get("tournament")
_T_STEPS = [
    ("t_config",   "Configurar torneo",  "Nombre, categoría, formato y pistas",  _T_OBJ is not None),
    ("t_pairs",    "Añadir parejas",     "Registra las parejas participantes",   _T_OBJ is not None and len(_T_OBJ.pairs) > 0),
    ("t_generate", "Generar estructura", "Crea grupos y/o cuadro",               _T_OBJ is not None and len(_T_OBJ.matches) > 0),
    ("t_schedule", "Asignar horarios",   "Planificación automática",             _T_OBJ is not None and _T_OBJ.scheduled_count > 0),
    ("t_export",   "Exportar",           "Descarga el Excel del torneo",         _T_OBJ is not None and _T_OBJ.scheduled_count > 0),
]
_IS_TOURNAMENT = page in {s[0] for s in _T_STEPS}

_section_label("🏆 Torneos")
with st.sidebar.expander("Ver pasos del torneo →", expanded=_IS_TOURNAMENT):
    for _i, (_sk, _sl, _sh, _sd) in enumerate(_T_STEPS, 1):
        _nav(_sk, f"{_i}. {_sl}", done=_sd, active=(page==_sk), hint=_sh)

# ── Admin ──────────────────────────────────────────────────────────────────
if _db_ok and is_superadmin():
    st.sidebar.markdown('<hr style="border-color:#1e3a58;margin:.5rem 0">', unsafe_allow_html=True)
    _nav("admin", "🛠️ Administración", active=(page == "admin"))

# ── Badge Dry-Run ──────────────────────────────────────────────────────────
st.sidebar.markdown('<hr style="border-color:#1e3a58;margin:.8rem 0 .4rem">', unsafe_allow_html=True)
_dry = _s.get("dry_run", True)
_badge_cls = "pp-badge-safe" if _dry else "pp-badge-live"
_badge_txt = "🔒 DRY-RUN" if _dry else "⚡ ESCRITURA REAL"
st.sidebar.markdown(f'<div style="padding:0 10px"><span class="{_badge_cls}">{_badge_txt}</span></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TORNEOS — helpers (deben definirse antes del routing)
# ---------------------------------------------------------------------------

def _t_header(step_num: int, step_title: str, step_hint: str) -> None:
    import datetime as _dt_mod
    t = st.session_state.get("tournament")
    if t and t.is_top:
        _cat_html = ""
        if t.category:
            _cls = {"masculino":"t-cat-masc","femenino":"t-cat-fem","mixto":"t-cat-mix"}[t.category.value]
            _cat_html = f'<span class="{_cls}">{t.category.icon} {t.category.label}</span>'
        if t.subcategory:
            _cat_html += f'<span class="t-subcat">{t.subcategory.label}</span>'
        _dates = t.start_date.strftime("%d/%m/%Y") + (f" – {t.end_date.strftime('%d/%m/%Y')}" if t.end_date != t.start_date else "")
        st.markdown(
            f'<div class="t-top-banner"><div class="t-top-name">🏆 {t.name}</div>'
            f'<div class="t-top-meta">📅 {_dates}' + (f' &nbsp;|&nbsp; 📍 {t.location}' if t.location else '') + f'</div>'
            f'<div style="margin-top:.5rem">{_cat_html}</div>' + (f'<div class="t-top-prize">🥇 {t.prize}</div>' if t.prize else '') + f'</div>',
            unsafe_allow_html=True,
        )
    else:
        _page_header("🏆", f"Torneos — {step_title}", step_hint)
    _steps_bc = ["⚙️ Config","👥 Parejas","🎯 Estructura","🗓️ Horarios","📤 Exportar"]
    _bc_html = '<div style="display:flex;gap:6px;margin-bottom:1.4rem;flex-wrap:wrap">'
    for _i, _sbc in enumerate(_steps_bc, 1):
        if _i < step_num:
            _bc_html += f'<span style="background:#00c853;color:#fff;border-radius:20px;padding:3px 12px;font-size:.75rem;font-weight:700">✓ {_sbc}</span>'
        elif _i == step_num:
            _bc_html += f'<span style="background:#0b1a2b;color:#fff;border:2px solid #00c853;border-radius:20px;padding:3px 12px;font-size:.75rem;font-weight:700">▶ {_sbc}</span>'
        else:
            _bc_html += f'<span style="background:#e4edf8;color:#8faac8;border-radius:20px;padding:3px 12px;font-size:.75rem">○ {_sbc}</span>'
    _bc_html += '</div>'
    st.markdown(_bc_html, unsafe_allow_html=True)


def _t_nav_buttons(current_step: int) -> None:
    _keys = ["t_config","t_pairs","t_generate","t_schedule","t_export"]
    _col_prev, _, _col_next = st.columns([1, 4, 1])
    with _col_prev:
        if current_step > 1:
            if st.button("← Anterior", use_container_width=True, key=f"t_prev_{current_step}"):
                st.session_state["_nav_page"] = _keys[current_step - 2]; st.rerun()
    with _col_next:
        if current_step < len(_keys):
            if st.button("Siguiente →", type="primary", use_container_width=True, key=f"t_next_{current_step}"):
                st.session_state["_nav_page"] = _keys[current_step]; st.rerun()


# ---------------------------------------------------------------------------
# PÁGINA 0: Configuración del club
# ---------------------------------------------------------------------------

if page == "club_config":
    _page_header("🏢", "Configuración del club", "Datos del club que se guardan automáticamente")

    _cid = current_club_id() if _db_ok else None
    _club_row = _db.get_club_by_id(_cid) if (_db_ok and _db and _cid) else None

    # Leer settings guardados
    _settings = (_club_row.get("settings") or {}) if _club_row else {}

    col1, col2 = st.columns(2)
    with col1:
        _section_start("🏢", "Datos del club")
        _cc_name    = st.text_input("Nombre del club", value=_club_row["name"] if _club_row else _s.get("club_name",""))
        _cc_address = st.text_input("Dirección", value=_settings.get("address",""), placeholder="Calle Mayor 1, Madrid")
        _cc_phone   = st.text_input("Teléfono", value=_settings.get("phone",""),   placeholder="+34 600 000 000")
        _cc_email   = st.text_input("Email de contacto", value=_settings.get("email",""), placeholder="info@miclub.es")
        _cc_web     = st.text_input("Web", value=_settings.get("web",""),           placeholder="https://miclub.es")

    with col2:
        _section_start("🏟️", "Instalaciones")
        _cc_courts  = st.number_input("Número de pistas de pádel", min_value=1, max_value=30,
                                      value=int(_settings.get("num_courts", 4)))
        _cc_indoor  = st.number_input("Pistas cubiertas", min_value=0, max_value=30,
                                      value=int(_settings.get("indoor_courts", 0)))
        _section_start("⏰", "Horario de apertura")
        _cc_open  = st.time_input("Apertura",  value=_settings.get("open_time",  "08:00") if isinstance(_settings.get("open_time"), str) else time(8,0))
        _cc_close = st.time_input("Cierre",    value=_settings.get("close_time", "23:00") if isinstance(_settings.get("close_time"), str) else time(23,0))
        _cc_notes = st.text_area("Notas / descripción", value=_settings.get("notes",""),
                                 placeholder="Ej: Parking gratuito, vestuarios...", height=80)

    st.divider()
    if st.button("💾 Guardar configuración del club", type="primary", use_container_width=True):
        _new_settings = {
            "address": _cc_address, "phone": _cc_phone, "email": _cc_email,
            "web": _cc_web, "num_courts": _cc_courts, "indoor_courts": _cc_indoor,
            "open_time": str(_cc_open), "close_time": str(_cc_close), "notes": _cc_notes,
        }
        st.session_state["club_name"] = _cc_name
        if _db_ok and _db and _cid:
            try:
                # Guardar settings en la tabla clubs
                _db._c.table("clubs").update({"name": _cc_name, "settings": _new_settings}).eq("id", _cid).execute()
                st.success("✅ Configuración del club guardada en la base de datos.")
            except Exception as _e:
                st.warning(f"⚠️ No se pudo guardar en BD: {_e}")
        else:
            st.success("✅ Configuración guardada en sesión.")

    if _club_row:
        st.info(
            f"🏢 **{_club_row['name']}** · "
            + (f"📍 {_settings.get('address','')}" if _settings.get('address') else "Añade la dirección arriba")
        )

    st.divider()
    st.markdown("#### 🚀 ¿Qué hacer a continuación?")
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("📊 Ir al Ranking →", type="primary", use_container_width=True):
            st.session_state["_nav_page"] = "config"; st.rerun()
    with cc2:
        if st.button("🏆 Ir a Torneos →", use_container_width=True):
            st.session_state["_nav_page"] = "t_config"; st.rerun()


# ---------------------------------------------------------------------------
# PÁGINA 1: Configuración
# ---------------------------------------------------------------------------

elif page == "config":
    _page_header("⚙️", "Configuración", "Credenciales de Syltek y parámetros de la fase de ranking")
    st.info("Las credenciales se leen del archivo `.env`. Aquí configuras los parámetros de la fase.")

    col1, col2 = st.columns(2)

    with col1:
        _section_start("🔌", "Credenciales Syltek")
        syltek_url = st.text_input(
            "URL de Syltek",
            value=settings.syltek_url or "https://padelplus.padelclick.com",
            help="Solo la URL base, sin path. Ej: https://padelplus.padelclick.com",
        )
        syltek_user = st.text_input("Usuario", value=settings.syltek_user or "")
        syltek_pass = st.text_input("Contraseña", type="password", value="")

        dry_run = st.toggle("Modo Dry-Run (sin escritura real)", value=True)
        st.session_state.dry_run = dry_run

        if st.button("🔌 Comprobar login con Syltek"):
            if not syltek_url or not syltek_user or not syltek_pass:
                st.error("Rellena URL, usuario y contraseña antes de probar.")
            else:
                with st.spinner("Intentando login... (puede tardar 15–30 segundos)"):
                    ok, msg = run_login_check(syltek_url, syltek_user, syltek_pass)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
                    st.info(
                        "Revisa los selectores en `src/syltek_connector.py` "
                        "y las capturas en `debug/screenshots/`."
                    )

    with col2:
        _section_start("📅", "Parámetros de la fase")
        phase_name = st.text_input("Nombre de la fase", value="Fase 1")
        start_date = st.date_input("Fecha de inicio", value=date.today() + timedelta(days=7))
        end_date = st.date_input("Fecha de fin", value=date.today() + timedelta(days=42))

        col2a, col2b = st.columns(2)
        with col2a:
            start_hour = st.time_input("Hora mínima de juego", value=time(16, 0))
        with col2b:
            end_hour = st.time_input("Hora máxima de juego", value=time(22, 30))

        match_duration = st.slider("Duración del partido (min)", 60, 120, 90, step=30)
        n_courts = st.slider("Número de pistas disponibles", 1, 12, 4)
        max_per_week = st.slider("Máx. partidos por pareja/semana", 1, 5, 1)
        min_days_between = st.slider(
            "Mín. días entre partidos de una misma pareja",
            0, 7, 2,
            help="0 = sin restricción. Evita que una pareja juegue dos días seguidos.",
        )
        seed_enabled = st.checkbox(
            "Asignación reproducible (semilla fija)",
            value=True,
            help="Si está activado, generar el calendario dos veces con la misma config da el mismo resultado.",
        )
        random_seed_val = st.number_input("Semilla", value=42, step=1) if seed_enabled else None
        club_name = st.text_input("Nombre del club", value="Mi Club de Pádel")

        if st.button("💾 Guardar configuración de fase"):
            errs = validate_phase_dates(start_date, end_date)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                from uuid import uuid4 as _uuid4
                from src.models import BalanceWeights
                courts = [
                    Court.model_construct(id=f"court_{i}", name=f"Pista {i}", indoor=False, active=True)
                    for i in range(1, n_courts + 1)
                ]
                phase = RankingPhase.model_construct(
                    id=str(_uuid4()),
                    name=phase_name,
                    start_date=start_date,
                    end_date=end_date,
                    courts=courts,
                    groups=st.session_state.groups,
                    bookings=st.session_state.bookings,
                    match_duration_minutes=match_duration,
                    day_start_time=start_hour,
                    day_end_time=end_hour,
                    max_matches_per_week=max_per_week,
                    min_days_between_matches=min_days_between,
                    random_seed=int(random_seed_val) if random_seed_val is not None else None,
                    balance_weights=BalanceWeights.model_construct(
                        same_hour_penalty=10.0,
                        same_weekday_penalty=6.0,
                        same_court_penalty=2.0,
                        day_load_penalty=1.5,
                        court_load_penalty=1.0,
                        early_day_bonus=0.5,
                        preferred_slot_bonus=25.0,
                        global_hour_penalty=5.0,
                        global_weekday_penalty=4.0,
                        late_hour_penalty=2.5,
                        top_candidates_pool=4,
                    ),
                )
                st.session_state.phase = phase
                st.session_state.courts = courts
                st.session_state["club_name"] = club_name

                # Persistir en Supabase si está configurado
                if _db_ok and _db is not None:
                    _cid = current_club_id()
                    if _cid:
                        try:
                            _payload = phase_to_db(phase, _cid, st.session_state.get("db_phase_id"))
                            _saved = _db.upsert_phase(
                                club_id=_cid,
                                name=_payload["name"],
                                start_date=_payload["start_date"],
                                end_date=_payload["end_date"],
                                phase_config=_payload["phase_config"],
                                groups_data=_payload["groups_data"],
                                bookings_data=_payload["bookings_data"],
                                schedule_result=None,
                                phase_id=_payload["phase_id"],
                            )
                            st.session_state["db_phase_id"] = _saved["id"]
                        except Exception as _e:
                            st.warning(f"⚠️ No se pudo guardar en BD: {_e}")

                st.success("✅ Configuración guardada.")

# ---------------------------------------------------------------------------
# PÁGINA 2: Importar datos
# ---------------------------------------------------------------------------

elif page == "import":
    _page_header("📥", "Importar datos", "Carga grupos, parejas y reservas desde CSV o directamente desde Syltek")
    st.info("Carga grupos y parejas desde CSV. También puedes importar reservas existentes.")

    tab1, tab2, tab3 = st.tabs(["👥 Grupos y parejas", "📋 Reservas existentes", "🔌 Desde Syltek"])

    # --- Tab 1: Grupos desde CSV ---
    with tab1:
        st.markdown("**Formato esperado del CSV:**")
        st.code(
            "group_id, group_name, level, pair_name, player1_name, player1_email, "
            "player1_phone, player2_name, player2_email, player2_phone",
            language="text",
        )
        st.download_button(
            "⬇️ Descargar CSV de ejemplo",
            data=(_HERE / "sample_data" / "groups_example.csv").read_text(encoding="utf-8"),
            file_name="groups_example.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader("Sube tu CSV de grupos", type=["csv"])
        if uploaded:
            df = pd.read_csv(uploaded)
            errs = validate_groups_df(df)
            if errs:
                st.error("Errores en el CSV:")
                for e in errs:
                    st.write(f"- {e}")
            else:
                groups = _df_to_groups(df)
                st.session_state.groups = groups
                st.session_state.data_loaded = True
                # Actualizar fase si existe
                if st.session_state.phase:
                    st.session_state.phase.groups = groups
                    # Persistir en Supabase
                    if _db_ok and _db is not None:
                        _cid = current_club_id()
                        _pid = st.session_state.get("db_phase_id")
                        if _cid and _pid:
                            try:
                                _ph = st.session_state.phase
                                _payload = phase_to_db(_ph, _cid, _pid)
                                _db.upsert_phase(
                                    club_id=_cid,
                                    name=_payload["name"],
                                    start_date=_payload["start_date"],
                                    end_date=_payload["end_date"],
                                    phase_config=_payload["phase_config"],
                                    groups_data=_payload["groups_data"],
                                    bookings_data=_payload["bookings_data"],
                                    schedule_result=schedule_result_to_db(st.session_state.schedule_result),
                                    phase_id=_pid,
                                )
                            except Exception:
                                pass
                st.success(f"✅ {len(groups)} grupos cargados con {sum(len(g.pairs) for g in groups)} parejas.")

        if st.session_state.groups:
            _section_start("👥", "Vista previa de grupos")
            for g in st.session_state.groups:
                with st.expander(f"{g.name} — {len(g.pairs)} parejas"):
                    rows = []
                    for p in g.pairs:
                        rows.append({
                            "Pareja": p.display_name,
                            "Jugador 1": p.player_1.full_name,
                            "Email 1": p.player_1.email or "",
                            "Tel 1": p.player_1.phone or "",
                            "Jugador 2": p.player_2.full_name,
                            "Email 2": p.player_2.email or "",
                            "Tel 2": p.player_2.phone or "",
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # --- Tab 2: Reservas ---
    with tab2:
        st.markdown("**Formato esperado del CSV de reservas:**")
        st.code("court_id, court_name, start_datetime, end_datetime, description, source", language="text")
        st.download_button(
            "⬇️ Descargar CSV de ejemplo (reservas)",
            data=(_HERE / "sample_data" / "bookings_example.csv").read_text(encoding="utf-8"),
            file_name="bookings_example.csv",
            mime="text/csv",
        )

        uploaded_b = st.file_uploader("Sube tu CSV de reservas", type=["csv"], key="bookings_upload")
        if uploaded_b:
            df_b = pd.read_csv(uploaded_b)
            errs_b = validate_bookings_df(df_b)
            if errs_b:
                for e in errs_b:
                    st.error(e)
            else:
                bookings = _df_to_bookings(df_b)
                st.session_state.bookings = bookings
                if st.session_state.phase:
                    st.session_state.phase.bookings = bookings
                st.success(f"✅ {len(bookings)} reservas cargadas.")

        if st.session_state.bookings:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Pista": b.court_name,
                        "Inicio": b.start_datetime,
                        "Fin": b.end_datetime,
                        "Descripción": b.description,
                    }
                    for b in st.session_state.bookings
                ]),
                use_container_width=True,
            )

    # --- Tab 3: Syltek ---
    with tab3:
        st.markdown("### Conectar con Syltek")

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            syl_imp_url = st.text_input(
                "URL Syltek",
                value=settings.syltek_url or "https://padelplus.padelclick.com",
                key="syl_imp_url",
            )
            syl_imp_user = st.text_input(
                "Usuario",
                value=settings.syltek_user or "",
                key="syl_imp_user",
            )
        with col_c2:
            syl_imp_pass = st.text_input("Contraseña", type="password", key="syl_imp_pass")

        st.markdown("---")

        # ---- A: Importar grupos y parejas ----
        st.markdown("#### 👥 Importar grupos y parejas del ranking")
        st.info(
            "Lee directamente desde Syltek los grupos, jugadores y disponibilidad "
            "de todos los niveles. URL utilizada: `/rankings/showtab/{id}/group{rotacion}`"
        )

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            level_ids_str = st.text_input(
                "IDs de los niveles (separados por comas)",
                value="101, 102, 103, 104, 105, 106, 107",
                key="grp_level_ids",
                help="Los IDs de cada nivel de ranking en Syltek (p.ej. 101 = Nivel 1).",
            )
        with col_r2:
            grp_rotation = st.number_input(
                "Número de grupo (rotación)",
                value=5,
                min_value=1,
                max_value=20,
                key="grp_rotation",
                help="El número de grupo/rotación que aparece en la URL: group{N}.",
            )

        if st.button("👥 Importar grupos desde Syltek", type="primary", key="btn_import_groups"):
            if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                st.error("Rellena URL, usuario y contraseña.")
            else:
                try:
                    level_ids = [int(x.strip()) for x in level_ids_str.split(",") if x.strip()]
                except ValueError:
                    st.error("IDs de niveles inválidos. Usa números separados por comas (ej: 101, 102).")
                    level_ids = []

                if level_ids:
                    conn_grp = SyltekConnector(
                        url=syl_imp_url, user=syl_imp_user, password=syl_imp_pass, dry_run=True
                    )
                    ok, msg = conn_grp.login()
                    if not ok:
                        st.error(f"❌ Login fallido: {msg}")
                    else:
                        progress_grp = st.progress(0, text="Leyendo niveles del ranking...")
                        status_grp = st.empty()

                        def _update_grp(done, total, info=""):
                            progress_grp.progress(done / total, text=f"Nivel {done}/{total}... {info}")
                            status_grp.caption(info)

                        try:
                            groups_imp = conn_grp.read_all_levels(
                                level_ids=level_ids,
                                rotation=int(grp_rotation),
                                progress_callback=_update_grp,
                            )
                        except Exception as _e_grp:
                            groups_imp = []
                            st.error(f"❌ Error al leer los niveles: {_e_grp}")
                        progress_grp.empty()
                        status_grp.empty()

                        if groups_imp:
                            st.session_state.groups = groups_imp
                            st.session_state.data_loaded = True
                            if st.session_state.phase:
                                st.session_state.phase.groups = groups_imp
                            n_pairs_imp = sum(len(g.pairs) for g in groups_imp)
                            st.success(
                                f"✅ {len(groups_imp)} grupos y {n_pairs_imp} parejas importados correctamente."
                            )
                            day_names = ["L", "M", "X", "J", "V", "S", "D"]
                            with st.expander("Ver grupos importados"):
                                for g in groups_imp:
                                    st.markdown(f"**{g.name}** — {len(g.pairs)} parejas")
                                    for p in g.pairs:
                                        if getattr(p, "manual_only", False):
                                            st.write(f"  • {p.display_name}  📋 **[ASIGNACIÓN MANUAL]**")
                                        else:
                                            avail = ""
                                            if p.available_weekdays:
                                                avail += ", ".join(day_names[d] for d in p.available_weekdays)
                                            if p.available_from or p.available_until:
                                                avail += f"  {p.available_from or '?'} → {p.available_until or '?'}"
                                            st.write(f"  • {p.display_name}" + (f"  [{avail.strip()}]" if avail.strip() else ""))
                        else:
                            st.warning(
                                "No se encontraron grupos. Revisa los IDs de niveles y el número de rotación."
                            )

        # ---- Diagnóstico: valores columna Grupo ----
        with st.expander("🔎 Diagnóstico — valores columna Grupo por nivel"):
            diag_level_id2 = st.number_input("ID de nivel", value=101, step=1, key="diag_level_id2")
            diag_rotation2 = st.number_input("Rotación", value=int(grp_rotation), step=1, key="diag_rotation2")
            if st.button("🔎 Ver valores del campo Grupo", key="btn_diag_grupo"):
                if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                    st.error("Rellena URL, usuario y contraseña.")
                else:
                    _conn2 = SyltekConnector(url=syl_imp_url, user=syl_imp_user, password=syl_imp_pass, dry_run=True)
                    ok2, _msg2 = _conn2.login()
                    if not ok2:
                        st.error(f"❌ Login fallido: {_msg2}")
                    else:
                      try:
                        _url2 = f"{_conn2.base}/rankings/showtab/{int(diag_level_id2)}/group{int(diag_rotation2)}"
                        _r2 = _conn2._session.get(_url2, timeout=20)
                        from bs4 import BeautifulSoup as _BS2
                        _soup2 = _BS2(_r2.text, "html.parser")
                        _tables2 = _soup2.find_all("table")
                        st.write(f"**Tablas encontradas:** {len(_tables2)}")
                        for _ti, _tbl2 in enumerate(_tables2, 1):
                            _rows2 = _tbl2.find_all("tr")
                            if not _rows2:
                                continue
                            _hdrs2 = [c.get_text(strip=True) for c in _rows2[0].find_all(["th","td"])]
                            st.write(f"**Tabla {_ti} — cabecera:** `{_hdrs2}`")
                            # Mostrar todas las filas con sus valores
                            _data_rows = []
                            for _row2 in _rows2[1:]:
                                _cells2 = [c.get_text(strip=True) for c in _row2.find_all(["td","th"])]
                                if any(_cells2):
                                    _data_rows.append(_cells2)
                            import pandas as _pd2
                            if _data_rows:
                                _df_diag = _pd2.DataFrame(_data_rows, columns=(_hdrs2[:len(_data_rows[0])] if _hdrs2 else None))
                                # Resumen por grupo
                                if "Grupo" in _df_diag.columns:
                                    _vc = _df_diag["Grupo"].value_counts().sort_index()
                                    st.write(f"**Grupos únicos encontrados:** {sorted(_df_diag['Grupo'].unique().tolist())}")
                                    st.write(f"**Parejas por grupo:**")
                                    st.dataframe(_vc.rename("Parejas"), use_container_width=True)
                                # Tabla completa
                                st.dataframe(_df_diag, use_container_width=True, height=600)
                      except Exception as _e2:
                          st.error(f"❌ Error en diagnóstico: {_e2}")

        # ---- Diagnóstico: ver HTML del nivel ----
        with st.expander("🔎 Diagnóstico — ver estructura HTML de un nivel"):
            diag_level_id = st.number_input("ID de nivel a inspeccionar", value=101, step=1, key="diag_level_id")
            diag_rotation = st.number_input("Rotación", value=int(grp_rotation), step=1, key="diag_rotation_html")
            if st.button("🔎 Ver HTML del nivel", key="btn_diag_level"):
                if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                    st.error("Rellena URL, usuario y contraseña.")
                else:
                    _conn_d = SyltekConnector(url=syl_imp_url, user=syl_imp_user, password=syl_imp_pass, dry_run=True)
                    ok_d, msg_d = _conn_d.login()
                    if not ok_d:
                        st.error(f"Login fallido: {msg_d}")
                    else:
                      try:
                        _url_d = f"{_conn_d.base}/rankings/showtab/{int(diag_level_id)}/group{int(diag_rotation)}"
                        _r_d = _conn_d._session.get(_url_d, timeout=20)
                        from bs4 import BeautifulSoup as _BS
                        _soup_d = _BS(_r_d.text, "html.parser")
                        import re as _re
                        _hrx = _re.compile(r"\bgrupo\s*\d+\b", _re.I)
                        # 1. Headings con "Grupo"
                        _headings_info = []
                        for _tag in _soup_d.find_all(["h1","h2","h3","h4","h5","h6"]):
                            _txt = _tag.get_text(strip=True)
                            if _hrx.search(_txt):
                                _headings_info.append(f"<{_tag.name}>: '{_txt}'")
                        st.write(f"**Headings h1-h6 con 'Grupo':** {_headings_info or 'NINGUNO'}")
                        # 2. Tablas
                        _tables = _soup_d.find_all("table")
                        st.write(f"**Tablas encontradas:** {len(_tables)}")
                        for _i, _t in enumerate(_tables, 1):
                            _rows = _t.find_all("tr")
                            _hdr = [c.get_text(strip=True) for c in (_rows[0].find_all(["th","td"]) if _rows else [])]
                            st.write(f"  Tabla {_i}: {len(_rows)} filas · cabecera: `{_hdr[:10]}`")
                        # 3. HTML alrededor de cada aparición de "Grupo N"
                        _html_full = _r_d.text
                        _matches_g = list(_re.finditer(r"grupo\s*\d+", _html_full, _re.I))
                        st.write(f"**Apariciones de 'Grupo N' en el HTML:** {len(_matches_g)}")
                        if _matches_g:
                            # Mostrar contexto de las primeras 6 apariciones
                            _snippets = []
                            for _mx in _matches_g[:6]:
                                _s = max(0, _mx.start() - 80)
                                _e = min(len(_html_full), _mx.end() + 80)
                                _snippets.append(_html_full[_s:_e].replace("\n", " "))
                            st.code("\n---\n".join(_snippets), language="html")
                      except Exception as _e_d:
                          st.error(f"❌ Error en diagnóstico HTML: {_e_d}")

        st.markdown("---")

        # ---- B: Importar reservas existentes ----
        st.markdown("#### 📅 Importar reservas existentes del calendario")
        st.info(
            "Lee el calendario de Syltek para saber qué pistas ya están ocupadas "
            "cada día. El planificador asignará los partidos **solo a huecos libres**."
        )

        if not st.session_state.phase:
            st.warning("Guarda primero la configuración de fase (fechas, pistas) en **⚙️ Configuración**.")
        else:
            phase_tmp = st.session_state.phase
            st.markdown(f"**Rango de la fase:** {phase_tmp.start_date} → {phase_tmp.end_date}")
            n_days = (phase_tmp.end_date - phase_tmp.start_date).days + 1
            st.caption(f"Se leerán {n_days} días del calendario de Syltek")

            # ---- Diagnóstico: ver HTML bruto de un día ----
            with st.expander("🔎 Diagnóstico — ver HTML del calendario (un día)"):
                diag_date = st.date_input(
                    "Día a inspeccionar",
                    value=date.today(),
                    key="diag_date",
                )
                if st.button("🔎 Obtener HTML de ese día", key="btn_diag"):
                    if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                        st.error("Rellena URL, usuario y contraseña en la sección superior.")
                    else:
                        import base64 as _b64
                        conn_diag = SyltekConnector(
                            url=syl_imp_url, user=syl_imp_user, password=syl_imp_pass, dry_run=True
                        )
                        ok_d, msg_d = conn_diag.login()
                        if not ok_d:
                            st.error(f"❌ Login fallido: {msg_d}")
                        else:
                            encoded = _b64.b64encode(diag_date.strftime("%d/%m/%Y").encode()).decode()
                            url_cal = f"{conn_diag.base}/bookings/admin/index?encodedDate={encoded}&type=56"
                            st.caption(f"URL consultada: `{url_cal}`")
                            try:
                                r_diag = conn_diag._session.get(url_cal, timeout=20)
                                st.caption(f"HTTP {r_diag.status_code} — {len(r_diag.text):,} caracteres")
                                from bs4 import BeautifulSoup as _BS
                                soup_d = _BS(r_diag.text, "html.parser")

                                # 1) Clases CSS presentes que contengan palabras clave
                                all_cls: set = set()
                                for _tag in soup_d.find_all(True):
                                    for _c in (_tag.get("class") or []):
                                        all_cls.add(_c)
                                rel_cls = sorted(
                                    c for c in all_cls
                                    if any(k in c.lower() for k in ("timetable","booking","reserv","cell","slot","court","pista"))
                                )
                                st.markdown(f"**Clases relevantes ({len(rel_cls)}):**")
                                st.code(", ".join(rel_cls) or "(ninguna)", language="text")

                                # 2) Mostrar el elemento timetableTabsOuter si existe
                                tabs_outer = soup_d.find(class_=lambda c: c and "timetableTabsOuter" in c)
                                if tabs_outer:
                                    st.markdown("**Elemento timetableTabsOuter:**")
                                    st.code(str(tabs_outer)[:3000], language="html")

                                # 3) Probar el nuevo parser directamente (pasamos HTML crudo)
                                st.markdown("**Resultado del parser de reservas:**")
                                parsed_bk = _parse_occupied_slots(r_diag.text, diag_date)
                                # Mostrar siempre el objeto timetable JS (primeros 4000 chars)
                                raw_d = r_diag.text
                                m_tt = re.search(r'var\s+timetable\s*=\s*\{', raw_d)
                                if m_tt:
                                    st.markdown("**Objeto `var timetable` (primeros 4000 chars):**")
                                    st.code(raw_d[m_tt.start():m_tt.start()+4000], language="javascript")
                                else:
                                    st.error("No se encontró 'var timetable' en el HTML.")

                                if parsed_bk:
                                    st.success(f"✅ {len(parsed_bk)} reservas detectadas por el parser.")
                                    df_bk_diag = pd.DataFrame([
                                        {
                                            "Pista": b.court_name,
                                            "Inicio": b.start_datetime.strftime("%H:%M"),
                                            "Fin": b.end_datetime.strftime("%H:%M"),
                                        }
                                        for b in parsed_bk
                                    ])
                                    st.dataframe(df_bk_diag, use_container_width=True)
                                else:
                                    st.warning("Parser devolvió 0 reservas — revisa el objeto JS de arriba.")
                            except Exception as ex:
                                st.error(f"Error: {ex}")

            if st.button("📅 Importar disponibilidad desde Syltek", type="primary"):
                if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                    st.error("Rellena URL, usuario y contraseña en la sección superior.")
                else:
                    conn_bk = SyltekConnector(
                        url=syl_imp_url, user=syl_imp_user, password=syl_imp_pass, dry_run=True
                    )
                    ok, msg = conn_bk.login()
                    if not ok:
                        st.error(f"❌ Login fallido: {msg}")
                    else:
                        progress_bar = st.progress(0, text="Leyendo calendario de Syltek...")
                        status_text = st.empty()

                        def _update_bk(done, total):
                            pct = (done / total) if total > 0 else 1.0
                            progress_bar.progress(min(pct, 1.0), text=f"Leyendo día {done} de {total}...")
                            status_text.caption(f"Procesado: {done}/{total} días")

                        try:
                            bookings = conn_bk.get_bookings_range(
                                from_date=phase_tmp.start_date,
                                to_date=phase_tmp.end_date,
                                progress_callback=_update_bk,
                            )
                        except Exception as _e_bk:
                            bookings = []
                            st.error(f"❌ Error al importar reservas: {_e_bk}")

                        progress_bar.empty()
                        status_text.empty()

                        st.session_state.bookings = bookings
                        if st.session_state.phase:
                            st.session_state.phase.bookings = bookings

                        if bookings:
                            st.success(
                                f"✅ {len(bookings)} reservas existentes importadas. El planificador las respetará."
                            )
                            # CSV de TODAS las reservas (sin límite)
                            rows_all = [
                                {
                                    "Pista": b.court_name,
                                    "Fecha": b.start_datetime.strftime("%d/%m/%Y"),
                                    "Día": ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"][b.start_datetime.weekday()],
                                    "Inicio": b.start_datetime.strftime("%H:%M"),
                                    "Fin": b.end_datetime.strftime("%H:%M"),
                                    "Descripción": b.description[:80] if b.description else "",
                                }
                                for b in bookings
                            ]
                            df_all_bk = pd.DataFrame(rows_all)
                            csv_all = df_all_bk.to_csv(index=False, encoding="utf-8")
                            st.download_button(
                                f"⬇️ Descargar TODAS las reservas ({len(bookings)}) — CSV",
                                data=csv_all,
                                file_name="reservas_syltek_completo.csv",
                                mime="text/csv",
                            )
                            # Vista previa (primeras 200 para rendimiento)
                            PREVIEW_LIMIT = 200
                            with st.expander(
                                f"Ver reservas importadas"
                                f"{' (primeras ' + str(PREVIEW_LIMIT) + ' de ' + str(len(bookings)) + ')' if len(bookings) > PREVIEW_LIMIT else ''}"
                            ):
                                st.dataframe(
                                    pd.DataFrame(rows_all[:PREVIEW_LIMIT]),
                                    use_container_width=True,
                                )
                                if len(bookings) > PREVIEW_LIMIT:
                                    st.caption(
                                        f"Vista previa: {PREVIEW_LIMIT} de {len(bookings)} reservas. "
                                        f"Descarga el CSV para verlas todas. "
                                        f"El scheduler usa **todas** las reservas para bloquear pistas."
                                    )
                        else:
                            st.warning(
                                "No se encontraron reservas existentes en ese rango de fechas. "
                                "Puede ser normal si las fechas son futuras o si el parsing necesita ajuste."
                            )

# ---------------------------------------------------------------------------
# PÁGINA 3: Generar calendario
# ---------------------------------------------------------------------------

elif page == "generate":
    _page_header("📅", "Generar calendario", "Crea los enfrentamientos round-robin y asigna horarios automáticamente")

    if not st.session_state.data_loaded or not st.session_state.groups:
        _empty_state("📥", "Sin datos cargados",
                     "Ve a <strong>📥 Importar datos</strong> y carga los grupos de ranking primero.")
        st.stop()

    if not st.session_state.phase:
        _empty_state("⚙️", "Fase no configurada",
                     "Ve a <strong>⚙️ Configuración</strong> y guarda los parámetros de la fase primero.")
        st.stop()

    phase: RankingPhase = st.session_state.phase

    # ── Panel de calidad de datos (errores/avisos antes de generar)
    _dq_issues = validate_groups(phase.groups)
    _dq_summary = issues_summary(_dq_issues)
    if _dq_issues:
        _sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}
        with st.expander(
            f"{'🔴 Problemas en los datos' if _dq_summary['errors'] else '🟡 Avisos de datos'} "
            f"— {_dq_summary['errors']} error(es), {_dq_summary['warnings']} aviso(s), "
            f"{_dq_summary['infos']} info",
            expanded=_dq_summary["errors"] > 0,
        ):
            for _iss in _dq_issues:
                _icon = _sev_icon.get(_iss["severity"], "🔵")
                st.markdown(f"{_icon} {_iss['message']}")
        if _dq_summary["errors"] > 0:
            st.error(
                f"⛔ Hay {_dq_summary['errors']} error(es) en los datos. "
                "Corrígelos en el CSV antes de generar el calendario."
            )

    col1, col2 = st.columns([1, 2])

    with col1:
        _section_start("⚡", "Acciones")

        if st.button("⚡ Generar enfrentamientos", type="primary"):
            matches = generate_all_matches(phase.groups)
            st.session_state.matches = matches
            st.session_state.matches_generated = True
            st.session_state.matches_scheduled = False
            st.session_state.schedule_result = None
            st.session_state.pop("schedule_violations", None)
            st.success(f"✅ {len(matches)} enfrentamientos generados.")

        # Desglose de grupos y parejas
        with st.expander("🔎 Ver desglose por grupo", expanded=False):
            from math import comb
            total_pairs = sum(len(g.pairs) for g in phase.groups)
            total_expected = sum(comb(len(g.pairs), 2) for g in phase.groups)
            st.caption(f"**{len(phase.groups)} grupos · {total_pairs} parejas · {total_expected} partidos esperados**")
            rows_diag = []
            for g in sorted(phase.groups, key=lambda x: x.name):
                n = len(g.pairs)
                rows_diag.append({"Grupo": g.name, "Parejas": n, "Partidos esperados": comb(n, 2)})
            st.dataframe(rows_diag, use_container_width=True, hide_index=True)

        if st.session_state.matches_generated:
            if st.button("🗓️ Asignar horarios", type="primary"):
                with st.spinner("Asignando horarios... "):
                    scheduler = Scheduler(phase)
                    result = scheduler.schedule(st.session_state.matches)
                st.session_state.schedule_result = result
                st.session_state.matches_scheduled = True
                st.session_state.matches = result.scheduled + result.conflicts

                # Persistir resultado del calendario en Supabase
                if _db_ok and _db is not None:
                    _cid = current_club_id()
                    _pid = st.session_state.get("db_phase_id")
                    if _cid and _pid and st.session_state.phase:
                        try:
                            _ph = st.session_state.phase
                            _payload = phase_to_db(_ph, _cid, _pid)
                            _db.upsert_phase(
                                club_id=_cid,
                                name=_payload["name"],
                                start_date=_payload["start_date"],
                                end_date=_payload["end_date"],
                                phase_config=_payload["phase_config"],
                                groups_data=_payload["groups_data"],
                                bookings_data=_payload["bookings_data"],
                                schedule_result=schedule_result_to_db(result),
                                phase_id=_pid,
                            )
                        except Exception as _e:
                            st.warning(f"⚠️ No se pudo guardar el calendario en BD: {_e}")

                # Ejecutar validación automáticamente
                violations = validate_schedule(result, phase)
                st.session_state["schedule_violations"] = violations

                if result.conflict_count == 0:
                    st.success(f"✅ Todos los partidos asignados ({result.scheduled_count}).")
                else:
                    st.warning(
                        f"⚠️ {result.scheduled_count} partidos programados, "
                        f"{result.conflict_count} con conflictos."
                    )

        # ---- Botón exportar Excel (plantilla grupos) ----
        if st.session_state.matches_scheduled and st.session_state.schedule_result:
            st.markdown("---")
            if st.button("📥 Exportar Excel (plantilla grupos)", type="secondary"):
                with st.spinner("Generando Excel..."):
                    _path_xls = export_groups_to_template(
                        st.session_state.schedule_result, phase
                    )
                with open(_path_xls, "rb") as _f:
                    st.download_button(
                        "⬇️ Descargar Excel grupos",
                        data=_f.read(),
                        file_name=_path_xls.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_xls_gen",
                    )

    with col2:
        if st.session_state.matches:
            _section_start("📊", "Resumen")
            result: ScheduleResult = st.session_state.schedule_result
            if result:
                m1, m2, m3 = st.columns(3)
                m1.metric("✅ Programados", result.scheduled_count)
                m2.metric("⚠️ Conflictos", result.conflict_count,
                          delta=f"-{result.conflict_count}" if result.conflict_count else None,
                          delta_color="inverse")
                m3.metric("🎯 Tasa de éxito", f"{result.success_rate:.1f}%")

                # ---- Panel rápido de validación ----
                violations = st.session_state.get("schedule_violations")

                if violations is not None:
                    vs = validation_summary(violations)
                    st.markdown("**Validación del calendario:**")
                    vc1, vc2, vc3 = st.columns(3)
                    vc1.metric("🔴 Errores",   vs["errors"])
                    vc2.metric("🟡 Avisos",    vs["warnings"])
                    vc3.metric("🔵 Info (PF)", vs["infos"])
                    if vs["total"] == 0:
                        st.success("✅ Sin incidencias — el calendario cumple todas las restricciones.")
                    else:
                        if vs["errors"] > 0:
                            st.error(f"⛔ Hay {vs['errors']} error(es) críticos. Revísalos en la página **🔍 Revisión**.")
                        elif vs["warnings"] > 0:
                            st.warning(f"⚠️ Hay {vs['warnings']} aviso(s). Revísalos en **🔍 Revisión**.")
                        else:
                            st.info(f"ℹ️ {vs['infos']} nota(s) sobre pistas fijas. Ver **🔍 Revisión**.")

    if st.session_state.matches:
        _section_start("📋", "Calendario generado")

        # Filtros globales (aplican a ambas vistas)
        fc1, fc2, fc3 = st.columns(3)

        # These derived collections are rebuilt only when matches change, not on every render.
        # They are keyed by the number of matches so a reschedule invalidates the cache.
        _cache_key = len(st.session_state.matches)
        if st.session_state.get("_filter_cache_key") != _cache_key:
            _matches = st.session_state.matches
            st.session_state["_filter_cache_key"] = _cache_key
            st.session_state["_group_names"] = sorted({m.group_name for m in _matches})
            st.session_state["_pair_names"] = sorted(
                {m.pair_1.display_name for m in _matches} | {m.pair_2.display_name for m in _matches}
            )
            st.session_state["_match_id_to_obj"] = {m.id: m for m in _matches}
            _court_name_to_obj: dict = {}
            for c in (st.session_state.courts or []):
                _court_name_to_obj[c.name] = c
            for m in _matches:
                if m.court and m.court.name not in _court_name_to_obj:
                    _court_name_to_obj[m.court.name] = m.court
            st.session_state["_court_name_to_obj"] = _court_name_to_obj

        group_names = st.session_state["_group_names"]
        pair_names  = st.session_state["_pair_names"]
        match_id_to_obj    = st.session_state["_match_id_to_obj"]
        court_name_to_obj  = st.session_state["_court_name_to_obj"]
        court_names = sorted(court_name_to_obj.keys())

        sel_group = fc1.multiselect("Filtrar por grupo", group_names, default=group_names)
        status_opts = [s.value for s in MatchStatus]
        sel_status = fc2.multiselect("Estado", status_opts, default=status_opts)
        sel_pair = fc3.multiselect("Pareja (contiene)", pair_names, default=[])

        filtered = [
            m for m in st.session_state.matches
            if m.group_name in sel_group
            and m.status.value in sel_status
            and (not sel_pair or m.pair_1.display_name in sel_pair or m.pair_2.display_name in sel_pair)
        ]

        # Índice de IDs para poder mapear filas editadas → objetos Match
        filtered_ids = [m.id for m in filtered]

        view_tab1, view_tab2 = st.tabs(["📋 Tabla", "📅 Vista calendario"])

        # ----------------------------------------------------------------
        # TAB 1: Tabla editable
        # ----------------------------------------------------------------
        with view_tab1:
            rows = []
            for m in filtered:
                rows.append({
                    "ID": m.id[:8],
                    "Grupo": m.group_name,
                    "Pareja 1": m.pair_1.display_name,
                    "Pareja 2": m.pair_2.display_name,
                    "Fecha": m.suggested_date,
                    "Inicio": m.suggested_start_time,
                    "Fin": m.suggested_end_time,
                    "Pista": m.court.name if m.court else "",
                    "Estado": m.status.value,
                    "Observaciones": (m.conflict_reason if m.status == MatchStatus.CONFLICT else m.notes) or "",
                })

            df_matches = pd.DataFrame(rows)

            st.info("✏️ Edita directamente Fecha, Hora, Pista, Estado u Observaciones. Pulsa **Guardar cambios** para confirmar.")

            edited_df = st.data_editor(
                df_matches,
                column_config={
                    "ID": st.column_config.TextColumn("ID", disabled=True, width="small"),
                    "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
                    "Pareja 1": st.column_config.TextColumn("Pareja 1", disabled=True),
                    "Pareja 2": st.column_config.TextColumn("Pareja 2", disabled=True),
                    "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "Inicio": st.column_config.TimeColumn("Inicio", format="HH:mm"),
                    "Fin": st.column_config.TimeColumn("Fin", format="HH:mm"),
                    "Pista": st.column_config.SelectboxColumn("Pista", options=[""] + court_names),
                    "Estado": st.column_config.SelectboxColumn("Estado", options=[s.value for s in MatchStatus]),
                    "Observaciones": st.column_config.TextColumn("Observaciones"),
                },
                hide_index=True,
                use_container_width=True,
                height=500,
                key="matches_editor",
            )

            # Detectar cambios pendientes desde el estado del editor
            editor_state = st.session_state.get("matches_editor", {})
            edited_rows = editor_state.get("edited_rows", {})
            n_pending = len(edited_rows)

            col_save, col_hint = st.columns([1, 3])
            with col_save:
                save_clicked = st.button(
                    f"💾 Guardar cambios ({n_pending})" if n_pending else "💾 Guardar cambios",
                    type="primary" if n_pending else "secondary",
                    disabled=(n_pending == 0),
                )
            with col_hint:
                if n_pending:
                    st.warning(f"Hay {n_pending} partido(s) modificado(s) sin guardar.")

            if save_clicked and edited_rows:
                changed = 0
                for row_idx_raw, changes in edited_rows.items():
                    row_idx = int(row_idx_raw)
                    if row_idx >= len(filtered_ids):
                        continue
                    match_obj = match_id_to_obj.get(filtered_ids[row_idx])
                    if match_obj is None:
                        continue

                    user_set_status = False
                    schedule_fields_changed = False  # fecha, hora o pista
                    for col, new_val in changes.items():
                        if col == "Fecha" and new_val is not None:
                            if isinstance(new_val, str):
                                from datetime import datetime as _dt
                                match_obj.suggested_date = _dt.fromisoformat(new_val).date()
                            else:
                                match_obj.suggested_date = new_val
                            schedule_fields_changed = True
                        elif col == "Inicio" and new_val is not None:
                            if isinstance(new_val, str):
                                parts = new_val.split(":")
                                match_obj.suggested_start_time = time(int(parts[0]), int(parts[1]))
                            else:
                                match_obj.suggested_start_time = new_val
                            schedule_fields_changed = True
                        elif col == "Fin" and new_val is not None:
                            if isinstance(new_val, str):
                                parts = new_val.split(":")
                                match_obj.suggested_end_time = time(int(parts[0]), int(parts[1]))
                            else:
                                match_obj.suggested_end_time = new_val
                            schedule_fields_changed = True
                        elif col == "Pista" and new_val and new_val in court_name_to_obj:
                            match_obj.court = court_name_to_obj[new_val]
                            schedule_fields_changed = True
                        elif col == "Estado" and new_val:
                            try:
                                match_obj.status = MatchStatus(new_val)
                                user_set_status = True
                            except ValueError:
                                pass
                        elif col == "Observaciones":
                            match_obj.notes = str(new_val or "")
                            match_obj.conflict_reason = None

                    # Solo marcar MANUALLY_MODIFIED si se tocaron campos de programación
                    # (fecha/hora/pista). Las notas solas no cambian el estado del partido.
                    if not user_set_status and schedule_fields_changed:
                        match_obj.status = MatchStatus.MANUALLY_MODIFIED
                    changed += 1

                if changed:
                    st.success(f"✅ {changed} partido(s) guardado(s) correctamente.")
                    del st.session_state["matches_editor"]
                    # Invalidar caché de filtros para reflejar los cambios
                    st.session_state.pop("_filter_cache_key", None)
                    st.rerun()

            st.caption(f"Mostrando {len(filtered)} de {len(st.session_state.matches)} partidos.")

        # ----------------------------------------------------------------
        # TAB 2: Vista calendario semanal
        # ----------------------------------------------------------------
        with view_tab2:
            scheduled_filtered = [m for m in filtered if m.suggested_date]

            if not scheduled_filtered:
                st.info("No hay partidos con fecha asignada para mostrar en el calendario.")
            else:
                # Calcular rango de semanas disponibles
                all_dates = sorted({m.suggested_date for m in scheduled_filtered})
                min_date = all_dates[0]
                max_date = all_dates[-1]

                # Primer lunes del rango
                first_monday = min_date - timedelta(days=min_date.weekday())
                last_monday = max_date - timedelta(days=max_date.weekday())

                # Lista de semanas (lunes)
                week_starts = []
                d_iter = first_monday
                while d_iter <= last_monday:
                    week_starts.append(d_iter)
                    d_iter += timedelta(weeks=1)

                # Selector de semana
                cal_col1, cal_col2 = st.columns([2, 3])
                with cal_col1:
                    week_labels = [
                        f"Sem {i+1}  ({ws.strftime('%d/%m')} – {(ws + timedelta(days=6)).strftime('%d/%m')})"
                        for i, ws in enumerate(week_starts)
                    ]
                    sel_week_idx = st.selectbox(
                        "Semana",
                        range(len(week_starts)),
                        format_func=lambda i: week_labels[i],
                        key="cal_week_sel",
                    )
                with cal_col2:
                    # Resumen rápido de la semana seleccionada
                    ws = week_starts[sel_week_idx]
                    we = ws + timedelta(days=6)
                    week_ms = [m for m in scheduled_filtered if ws <= m.suggested_date <= we]
                    conflicts_week = [m for m in week_ms if m.status == MatchStatus.CONFLICT]
                    st.markdown(
                        f"**{len(week_ms)} partidos** esta semana"
                        + (f" · ⚠️ {len(conflicts_week)} conflictos" if conflicts_week else " · ✅ sin conflictos")
                    )

                selected_week_start = week_starts[sel_week_idx]
                calendar_html = _build_calendar_html(scheduled_filtered, selected_week_start)
                st.markdown(calendar_html, unsafe_allow_html=True)

                # Leyenda de colores por grupo
                group_colors_leg = [
                    "#1976d2", "#388e3c", "#f57c00", "#7b1fa2", "#c62828",
                    "#00838f", "#6d4c41", "#1565c0", "#2e7d32", "#ad1457",
                ]
                ws_sel = week_starts[sel_week_idx]
                we_sel = ws_sel + timedelta(days=6)
                week_group_ids = list(dict.fromkeys(
                    m.group_id for m in scheduled_filtered
                    if ws_sel <= m.suggested_date <= we_sel
                ))
                if week_group_ids:
                    st.markdown("---")
                    st.caption("Leyenda de grupos:")
                    leg_cols = st.columns(min(len(week_group_ids), 6))
                    group_name_map = {m.group_id: m.group_name for m in scheduled_filtered}
                    for i, gid in enumerate(week_group_ids):
                        color = group_colors_leg[i % len(group_colors_leg)]
                        gname = group_name_map.get(gid, gid)
                        leg_cols[i % len(leg_cols)].markdown(
                            f'<span style="display:inline-block;width:12px;height:12px;'
                            f'background:{color};border-radius:2px;margin-right:4px"></span>'
                            f'<small>{gname}</small>',
                            unsafe_allow_html=True,
                        )

# ---------------------------------------------------------------------------
# PÁGINA 4: Exportar
# ---------------------------------------------------------------------------

elif page == "export":
    _page_header("📤", "Exportar", "Descarga el calendario en Excel o genera mensajes para los jugadores")

    if not st.session_state.matches_scheduled:
        _empty_state("📅", "Calendario no generado",
                     "Ve a <strong>📅 Generar calendario</strong> y asigna los horarios primero.")
        st.stop()

    phase: RankingPhase = st.session_state.phase
    result: ScheduleResult = st.session_state.schedule_result
    club_name = st.session_state.get("club_name", "El Club")

    col1, col2 = st.columns(2)

    with col1:
        _section_start("📊", "Excel del calendario")

        # ---- Exportar formato tabla (existente) ----
        if st.button("Generar Excel (tabla)", type="secondary"):
            with st.spinner("Generando Excel..."):
                path = export_to_excel(result, phase)
            st.success(f"✅ Excel generado: `{path}`")
            with open(path, "rb") as f:
                st.download_button(
                    "⬇️ Descargar Excel (tabla)",
                    data=f.read(),
                    file_name=path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_excel_tabla",
                )

        st.markdown("---")

        # ---- Exportar formato plantilla del club ----
        st.markdown("**Formato plantilla del club**")
        st.caption(
            "Matriz triangular round-robin por grupo, una hoja por grupo. "
            "Verde = ya contabilizado · Blanco = programado · Rojo = conflicto."
        )
        if st.button("🏆 Generar Excel (plantilla grupos)", type="primary"):
            with st.spinner("Generando Excel con plantilla del club..."):
                path_tpl = export_groups_to_template(result, phase)
            st.success(f"✅ Excel de plantilla generado.")
            with open(path_tpl, "rb") as f:
                st.download_button(
                    "⬇️ Descargar plantilla grupos",
                    data=f.read(),
                    file_name=path_tpl.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_excel_plantilla",
                )

    with col2:
        _section_start("✉️", "Mensajes para jugadores")

        msg_type = st.radio("Tipo de mensaje", ["Por grupo", "Por pareja"], horizontal=True)
        include_court = st.checkbox("Incluir nombre de pista", value=True)

        with st.expander("✏️ Personalizar texto del mensaje", expanded=False):
            _def_intro_g = (
                "Hola a todos,\n\n"
                "Os dejamos los partidos programados para esta fase del ranking."
            )
            _def_intro_p = "Hola {pair_name},\n\nAquí tenéis vuestros partidos del ranking:"
            _def_outro = (
                "Por favor, revisad cualquier incidencia con {club_name}.\n\n"
                "¡Muchos ánimos y mucho pádel!\n\n– {club_name}"
            )
            _def_outro_p = "Ante cualquier duda, contactad con {club_name}.\n\n¡Mucha suerte!\n– {club_name}"

            st.caption(
                "Puedes usar `{club_name}` y `{group_name}` / `{pair_name}` como variables."
            )
            intro_default = _def_intro_g if msg_type == "Por grupo" else _def_intro_p
            outro_default = _def_outro if msg_type == "Por grupo" else _def_outro_p
            custom_intro = st.text_area(
                "Texto de introducción", value=intro_default, height=100,
                key=f"custom_intro_{msg_type}",
            )
            custom_outro = st.text_area(
                "Texto de cierre", value=outro_default, height=100,
                key=f"custom_outro_{msg_type}",
            )

        if st.button("✉️ Generar mensajes", type="primary"):
            import zipfile, io
            matches = st.session_state.matches
            if msg_type == "Por grupo":
                msgs = generate_all_group_messages(
                    phase.groups, matches, club_name,
                    intro_text=custom_intro, outro_text=custom_outro,
                    include_court=include_court,
                )
                # ZIP con todos los mensajes
                _zip_buf = io.BytesIO()
                with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
                    for gid, txt in msgs.items():
                        _zf.writestr(f"mensaje_{gid}.txt", txt.encode("utf-8"))
                st.download_button(
                    "⬇️ Descargar todos los mensajes (.zip)",
                    data=_zip_buf.getvalue(),
                    file_name="mensajes_grupos.zip",
                    mime="application/zip",
                    key="dl_all_groups_zip",
                )
                for gid, txt in msgs.items():
                    group = next((g for g in phase.groups if g.id == gid), None)
                    label = group.name if group else gid
                    n_matches = sum(
                        1 for m in matches
                        if m.group_id == gid and m.status == MatchStatus.SCHEDULED
                    )
                    with st.expander(f"📧 {label} — {n_matches} partido(s)"):
                        st.code(txt, language=None)
                        st.download_button(
                            "⬇️ .txt",
                            data=txt.encode("utf-8"),
                            file_name=f"mensaje_{label}.txt",
                            mime="text/plain",
                            key=f"dl_g_{gid}",
                        )
            else:
                msgs = generate_all_pair_messages(
                    phase.groups, matches, club_name,
                    intro_text=custom_intro, outro_text=custom_outro,
                    include_court=include_court,
                )
                # ZIP con todos los mensajes
                import zipfile, io as _io
                _zip_buf2 = _io.BytesIO()
                with zipfile.ZipFile(_zip_buf2, "w", zipfile.ZIP_DEFLATED) as _zf2:
                    for pid, txt in msgs.items():
                        _zf2.writestr(f"mensaje_{pid}.txt", txt.encode("utf-8"))
                st.download_button(
                    "⬇️ Descargar todos los mensajes (.zip)",
                    data=_zip_buf2.getvalue(),
                    file_name="mensajes_parejas.zip",
                    mime="application/zip",
                    key="dl_all_pairs_zip",
                )
                for pid, txt in msgs.items():
                    pair = next(
                        (p for g in phase.groups for p in g.pairs if p.id == pid), None
                    )
                    label = pair.display_name if pair else pid
                    n_matches = sum(
                        1 for m in matches
                        if (m.pair_1.id == pid or m.pair_2.id == pid)
                        and m.status == MatchStatus.SCHEDULED
                    )
                    with st.expander(f"📧 {label} — {n_matches} partido(s)"):
                        st.code(txt, language=None)
                        st.download_button(
                            "⬇️ .txt",
                            data=txt.encode("utf-8"),
                            file_name=f"mensaje_{label}.txt",
                            mime="text/plain",
                            key=f"dl_p_{pid}",
                        )

# ---------------------------------------------------------------------------
# PÁGINA 5: Revisión
# ---------------------------------------------------------------------------

elif page == "review":
    _page_header("🔍", "Revisión y diagnóstico", "Valida el calendario generado y analiza conflictos y distribución")

    if not st.session_state.schedule_result:
        _empty_state("🔍", "Sin datos para revisar",
                     "Ve a <strong>📅 Generar calendario</strong> y asigna los horarios primero.")
        st.stop()

    result: ScheduleResult = st.session_state.schedule_result
    phase: RankingPhase = st.session_state.phase

    # Métricas globales
    _section_start("📋", "Resumen general")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 Total partidos", result.total_matches)
    m2.metric("✅ Programados", result.scheduled_count)
    m3.metric("⚠️ Conflictos", result.conflict_count)
    m4.metric("🎯 Éxito", f"{result.success_rate:.1f}%")

    # ---- Validación post-asignación ----
    _section_start("🔎", "Validación del calendario")

    _n_scheduled = len([m for m in result.scheduled if m.suggested_date and m.suggested_start_time])
    st.caption(f"Se validarán {_n_scheduled} partidos programados de {result.total_matches} totales.")

    if st.button("🔄 Ejecutar validación completa", type="primary"):
        if _n_scheduled == 0:
            st.warning("No hay partidos programados con fecha y hora asignadas. Genera el calendario primero.")
        else:
            try:
                with st.spinner("Validando calendario..."):
                    violations = validate_schedule(result, phase)
                st.session_state["schedule_violations"] = violations
                st.rerun()
            except Exception as _val_err:
                st.error(f"❌ Error durante la validación: {_val_err}")
                import traceback
                st.code(traceback.format_exc(), language="text")

    violations = st.session_state.get("schedule_violations")
    if violations is None:
        st.info("Pulsa el botón para ejecutar la validación completa del calendario.")
    else:
        vs = validation_summary(violations)
        rv1, rv2, rv3, rv4 = st.columns(4)
        rv1.metric("Total incidencias", vs["total"])
        rv2.metric("🔴 Errores",  vs["errors"])
        rv3.metric("🟡 Avisos",   vs["warnings"])
        rv4.metric("🔵 Info PF",  vs["infos"])

        if vs["total"] == 0:
            st.success("✅ Sin incidencias — el calendario cumple todas las restricciones.")
        else:
            # Filtro de tipo
            type_labels = {
                "weekend_match":           "🔴 Partido en sábado/domingo",
                "player_double_day":       "🔴 Jugador con 2 partidos mismo día",
                "court_double_booking":    "🔴 Pista reservada doble",
                "availability_weekday":    "🟡 Día no disponible",
                "availability_time_early": "🟡 Hora demasiado temprana",
                "availability_time_late":  "🟡 Hora demasiado tarde",
                "min_days_violation":      "🟡 Separación mínima incumplida",
                "max_week_violation":      "🟡 Máximo semanal superado",
                "preferred_slot_mismatch": "🔵 Pista fija no respetada (PF)",
            }
            all_types = sorted({v["type"] for v in violations})
            sel_types = st.multiselect(
                "Filtrar por tipo",
                all_types,
                default=all_types,
                format_func=lambda t: type_labels.get(t, t),
            )
            filtered_v = [v for v in violations if v["type"] in sel_types]
            st.caption(f"Mostrando {len(filtered_v)} de {vs['total']} incidencias")

            rows_v = []
            for v in filtered_v:
                match_labels = " / ".join(
                    m.label for m in v.get("matches", [])[:2]
                )
                fecha = ""
                if v.get("matches"):
                    m0 = v["matches"][0]
                    if m0.suggested_date:
                        fecha = m0.suggested_date.strftime("%d/%m/%Y")
                    if m0.suggested_start_time:
                        fecha += f" {m0.suggested_start_time.strftime('%H:%M')}"
                rows_v.append({
                    "Sev.": SEVERITY_EMOJI.get(v["severity"], ""),
                    "Tipo": type_labels.get(v["type"], v["type"]),
                    "Descripción": v["description"],
                    "Partido(s)": match_labels,
                    "Fecha": fecha,
                })
            st.dataframe(
                pd.DataFrame(rows_v),
                use_container_width=True,
                hide_index=True,
                height=min(600, 60 + len(rows_v) * 35),
            )

            # Descarga CSV de incidencias
            csv_v = pd.DataFrame(rows_v).to_csv(index=False)
            st.download_button(
                "⬇️ Descargar incidencias CSV",
                data=csv_v,
                file_name="validacion_calendario.csv",
                mime="text/csv",
            )

    st.markdown("---")

    # Conflictos detallados
    if result.conflicts:
        _section_start("⚠️", "Partidos con conflicto")
        rows_c = [
            {
                "Grupo": m.group_name,
                "Partido": m.label,
                "Razón": m.conflict_reason or "",
            }
            for m in result.conflicts
        ]
        st.dataframe(pd.DataFrame(rows_c), use_container_width=True)
    else:
        st.success("✅ No hay conflictos.")

    # Distribución por día
    if result.scheduled:
        _section_start("📆", "Distribución por día")
        from collections import Counter
        # Clave de sort: fecha real (YYYY-MM-DD) para orden cronológico correcto
        _day_items = sorted(
            ((m.suggested_date, m.suggested_date.strftime("%a %d/%m"))
             for m in result.scheduled if m.suggested_date),
        )
        day_count: dict[str, int] = {}
        for _d, _label in _day_items:
            day_count[_label] = day_count.get(_label, 0) + 1
        df_days = pd.DataFrame(
            {"Día": list(day_count.keys()), "Partidos": list(day_count.values())}
        )
        st.bar_chart(df_days.set_index("Día"))

        # Balanceo: franja horaria y día de la semana
        _section_start("⚖️", "Balanceo del calendario")
        bm = balance_metrics(result)
        bc1, bc2 = st.columns(2)
        with bc1:
            st.caption("Partidos por franja horaria")
            df_hours = pd.DataFrame(
                {"Hora": [f"{h:02d}:00" for h in bm["hour_distribution"].keys()],
                 "Partidos": list(bm["hour_distribution"].values())}
            )
            st.bar_chart(df_hours.set_index("Hora"))
        with bc2:
            st.caption("Partidos por día de la semana")
            weekday_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            df_wd = pd.DataFrame(
                {"Día": [weekday_names[w] for w in bm["weekday_distribution"].keys()],
                 "Partidos": list(bm["weekday_distribution"].values())}
            )
            st.bar_chart(df_wd.set_index("Día"))

    # Distribución por pista
    if result.courts_used:
        _section_start("🏟️", "Pistas utilizadas")
        court_count = Counter(
            m.court.name for m in result.scheduled if m.court
        )
        df_courts = pd.DataFrame(
            {"Pista": list(court_count.keys()), "Partidos": list(court_count.values())}
        )
        st.bar_chart(df_courts.set_index("Pista"))

    # Parejas con más conflictos
    if result.conflict_details:
        _section_start("👥", "Parejas con más conflictos")
        from collections import defaultdict
        pair_map: dict[str, str] = {}
        for g in phase.groups:
            for p in g.pairs:
                pair_map[p.id] = p.display_name

        conflict_pairs = pairs_with_most_conflicts(result)
        rows_p = [
            {"Pareja": pair_map.get(pid, pid), "Conflictos": cnt}
            for pid, cnt in conflict_pairs
        ]
        st.dataframe(pd.DataFrame(rows_p), use_container_width=True)

# ---------------------------------------------------------------------------
# PÁGINA 6: Publicar en Syltek
# ---------------------------------------------------------------------------

elif page == "syltek":
    _page_header("🔗", "Publicar en Syltek", "Crea las reservas del ranking directamente en el sistema Syltek")


    # Estado de sesión Syltek
    if "syltek_logged_in" not in st.session_state:
        st.session_state["syltek_logged_in"] = False
    if "syltek_courts" not in st.session_state:
        st.session_state["syltek_courts"] = {}
    if "syltek_publish_results" not in st.session_state:
        st.session_state["syltek_publish_results"] = []

    # ----------------------------------------------------------------
    # Paso 1: Conexión
    # ----------------------------------------------------------------
    _step_header(1, "Conectar con Syltek")

    col_url, col_user = st.columns(2)
    with col_url:
        syl_url = st.text_input(
            "URL de Syltek",
            value=settings.syltek_url or "https://padelplus.padelclick.com",
            key="syl_url",
            help="Solo la URL base. Ej: https://padelplus.padelclick.com",
        )
    with col_user:
        syl_user = st.text_input(
            "Usuario",
            value=settings.syltek_user or "",
            key="syl_user",
        )
    syl_pass = st.text_input("Contraseña", type="password", key="syl_pass")

    dry_run_toggle = st.toggle(
        "Modo seguro (DRY-RUN) — simula las reservas sin crearlas de verdad",
        value=True,
        key="syl_dry_run",
    )
    if not dry_run_toggle:
        st.error("⚠️ Modo escritura REAL activado. Las reservas se crearán en Syltek.")

    if st.button("🔌 Conectar", type="primary"):
        if not syl_url or not syl_user or not syl_pass:
            st.error("Rellena URL, usuario y contraseña.")
        else:
            with st.spinner("Conectando con Syltek..."):
                ok, msg = run_login_check(syl_url, syl_user, syl_pass)
            if ok:
                st.session_state["syltek_logged_in"] = True
                st.session_state["syltek_credentials"] = (syl_url, syl_user, syl_pass)
                st.success(f"✅ {msg}")
            else:
                st.session_state["syltek_logged_in"] = False
                st.error(f"❌ {msg}")

    if not st.session_state["syltek_logged_in"]:
        st.stop()

    st.success("✅ Conectado a Syltek")
    st.markdown("---")

    # ----------------------------------------------------------------
    # Paso 2: Descubrir pistas
    # ----------------------------------------------------------------
    _step_header(2, "Descubrir pistas disponibles")
    st.info(
        "Esto conecta al calendario de Syltek y extrae automáticamente "
        "los nombres e IDs de todas las pistas."
    )

    col_disc, col_manual = st.columns(2)

    with col_disc:
        if st.button("🔍 Descubrir pistas automáticamente"):
            url_, user_, pass_ = st.session_state["syltek_credentials"]
            conn = SyltekConnector(url=url_, user=user_, password=pass_, dry_run=True)
            ok, msg = conn.login()
            if ok:
                with st.spinner("Leyendo calendario..."):
                    courts = conn.discover_courts()
                if courts:
                    st.session_state["syltek_courts"] = courts
                    st.success(f"✅ {len(courts)} pistas encontradas: {', '.join(courts.keys())}")
                else:
                    st.warning(
                        "No se pudieron detectar las pistas automáticamente. "
                        "Usa la configuración manual."
                    )
            else:
                st.error(msg)

    with col_manual:
        st.markdown("**O configura manualmente:**")
        n_courts = st.number_input("Número de pistas", min_value=1, max_value=20, value=10)
        if st.button("Configurar pistas manualmente"):
            manual_courts = {}
            for i in range(1, int(n_courts) + 1):
                manual_courts[f"Padel {i}"] = str(1479 + i)
            st.session_state["syltek_courts"] = manual_courts
            st.warning(
                "⚠️ Los IDs asignados (1480, 1481…) son **estimados** para Padelplus. "
                "Si las reservas fallan con error de pista, usa **🔍 Descubrir pistas automáticamente** "
                "para obtener los IDs reales de tu instalación."
            )

    if st.session_state["syltek_courts"]:
        with st.expander("Ver pistas configuradas"):
            for name, rid in st.session_state["syltek_courts"].items():
                st.write(f"• **{name}** → ID: `{rid}`")

        # Permitir edición manual de IDs
        st.markdown("**Corregir IDs si es necesario:**")
        courts_edit = {}
        cols = st.columns(5)
        for i, (name, rid) in enumerate(st.session_state["syltek_courts"].items()):
            with cols[i % 5]:
                new_id = st.text_input(name, value=rid, key=f"court_id_{i}", label_visibility="visible")
                courts_edit[name] = new_id
        if st.button("💾 Guardar IDs de pistas"):
            st.session_state["syltek_courts"] = courts_edit
            st.success("IDs guardados.")

    if not st.session_state["syltek_courts"]:
        st.stop()

    st.markdown("---")

    # ----------------------------------------------------------------
    # Paso 3: Publicar partidos
    # ----------------------------------------------------------------
    _step_header(3, "Crear reservas en Syltek")

    if not st.session_state.matches_scheduled:
        st.warning("Primero genera y asigna horarios en **Generar calendario**.")
        st.stop()

    phase: RankingPhase = st.session_state.phase
    scheduled = [m for m in st.session_state.matches if m.status.value in ("scheduled", "manually_modified")]

    st.metric("Partidos programados listos para publicar", len(scheduled))

    if not scheduled:
        st.info("No hay partidos programados. Genera el calendario primero.")
        st.stop()

    # Tabla resumen
    rows_pub = []
    for m in scheduled:
        rows_pub.append({
            "Grupo": m.group_name,
            "Pareja 1": m.pair_1.display_name,
            "Pareja 2": m.pair_2.display_name,
            "Fecha": m.suggested_date.strftime("%d/%m/%Y") if m.suggested_date else "—",
            "Hora": m.suggested_start_time.strftime("%H:%M") if m.suggested_start_time else "—",
            "Pista": m.court.name if m.court else "—",
        })
    st.dataframe(pd.DataFrame(rows_pub), use_container_width=True, height=300)

    send_email = st.checkbox("Enviar email de confirmación a los jugadores", value=False)

    mode_label = "🟠 SIMULACIÓN (dry-run)" if dry_run_toggle else "🔴 RESERVAS REALES"
    if st.button(f"🚀 Publicar {len(scheduled)} partidos en Syltek — {mode_label}", type="primary"):
        url_, user_, pass_ = st.session_state["syltek_credentials"]
        conn = SyltekConnector(url=url_, user=user_, password=pass_, dry_run=dry_run_toggle)
        with st.spinner("Reconectando con Syltek..."):
            ok_login, msg_login = conn.login()
        if not ok_login:
            st.error(f"❌ Sesión expirada o credenciales incorrectas: {msg_login}")
            st.info("Vuelve al Paso 1 y conéctate de nuevo.")
            st.stop()
        conn.set_courts(st.session_state["syltek_courts"])

        results = []
        progress = st.progress(0, text="Publicando partidos...")
        ok_count = 0
        fail_count = 0

        for i, match in enumerate(scheduled):
            if not match.suggested_date or not match.suggested_start_time or not match.court:
                results.append({"Partido": match.label, "Estado": "⚠️ Sin fecha/hora/pista", "Mensaje": ""})
                fail_count += 1
                continue

            try:
                ok, msg = conn.create_booking(
                    booking_date=match.suggested_date,
                    start_hour=match.suggested_start_time.hour,
                    start_minute=match.suggested_start_time.minute,
                    duration_minutes=phase.match_duration_minutes,
                    court_name=match.court.name,
                    pair1_name=match.pair_1.display_name,
                    pair2_name=match.pair_2.display_name,
                    group_name=match.group_name,
                    send_email=send_email,
                )
            except Exception as _e_pub:
                ok, msg = False, str(_e_pub)

            results.append({
                "Partido": match.label,
                "Estado": "✅ OK" if ok else "❌ Error",
                "Mensaje": msg,
            })
            if ok:
                ok_count += 1
            else:
                fail_count += 1

            progress.progress((i + 1) / len(scheduled), text=f"Publicando... {i+1}/{len(scheduled)}")

        progress.empty()
        st.session_state["syltek_publish_results"] = results

        if fail_count == 0:
            st.success(f"✅ {ok_count} reservas {'simuladas' if dry_run_toggle else 'creadas'} correctamente.")
        else:
            st.warning(f"✅ {ok_count} OK — ❌ {fail_count} errores")

    # Mostrar resultados anteriores
    if st.session_state["syltek_publish_results"]:
        _section_start("📊", "Resultados de publicación")
        df_res = pd.DataFrame(st.session_state["syltek_publish_results"])
        st.dataframe(df_res, use_container_width=True)

# ---------------------------------------------------------------------------
# TORNEO — PASO 1: Configuración
# ---------------------------------------------------------------------------

elif page == "t_config":
    import datetime as _dt_mod
    _t_header(1, "Configurar torneo", "Define nombre, categoría, formato y pistas")
    t = st.session_state.get("tournament")

    # ── Tipo de torneo ─────────────────────────────────────────────────────
    _section_start("⭐", "Tipo de torneo")
    t_is_top = st.toggle(
        "🏆 **Torneo TOP** — máximo nivel y visibilidad",
        value=t.is_top if t else False,
        help="Los Torneos TOP tienen diseño premium dorado.",
    )
    if t_is_top:
        st.markdown(
            '<div style="background:linear-gradient(90deg,#3b0f6e,#6a1b9a);border:1px solid #ffd700;'
            'border-radius:12px;padding:.6rem 1.2rem;color:#ffd700;font-weight:700;font-size:.9rem">'
            '★ Este torneo tendrá diseño dorado destacado</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    _section_start("🏆", "Datos del torneo")
    c1, c2 = st.columns(2)
    with c1:
        t_name     = st.text_input("Nombre del torneo", value=t.name if t else "Torneo PadelPlus 2025")
        t_location = st.text_input("📍 Sede / Club", value=t.location if t else "", placeholder="Club Pádel Madrid")
        t_prize    = st.text_input("🥇 Premio / Descripción", value=t.prize if t else "", placeholder="Trofeo + material deportivo")
    with c2:
        t_start  = st.date_input("Fecha de inicio", value=t.start_date if t else _dt_mod.date.today())
        t_end    = st.date_input("Fecha de fin", value=t.end_date if t else _dt_mod.date.today(), min_value=t_start)
        t_format = st.selectbox(
            "Formato",
            options=[TournamentFormat.GROUPS, TournamentFormat.BRACKET, TournamentFormat.GROUPS_BRACKET],
            format_func=lambda f: {
                TournamentFormat.GROUPS:         "🔄 Solo grupos (round-robin)",
                TournamentFormat.BRACKET:        "🪜 Solo cuadro eliminatorio",
                TournamentFormat.GROUPS_BRACKET: "🔄🪜 Grupos + cuadro final",
            }[f],
            index=0 if t is None else [TournamentFormat.GROUPS, TournamentFormat.BRACKET, TournamentFormat.GROUPS_BRACKET].index(t.format),
        )

    st.divider()
    _section_start("🎾", "Categoría")
    _cat_options = [None, TournamentCategory.MASCULINO, TournamentCategory.FEMENINO, TournamentCategory.MIXTO]
    _cat_labels  = {None: "⚪ Sin especificar", TournamentCategory.MASCULINO: "👨 Masculino", TournamentCategory.FEMENINO: "👩 Femenino", TournamentCategory.MIXTO: "🤝 Mixto"}
    _cur_cat = t.category if t else None
    t_category = st.radio("Categoría", options=_cat_options, format_func=lambda c: _cat_labels[c],
                          index=_cat_options.index(_cur_cat) if _cur_cat in _cat_options else 0,
                          horizontal=True, label_visibility="collapsed")
    if t_category:
        _bc = {"masculino": "t-cat-masc", "femenino": "t-cat-fem", "mixto": "t-cat-mix"}[t_category.value]
        st.markdown(f'<div style="margin:.4rem 0"><span class="{_bc}">{t_category.icon} {t_category.label}</span></div>', unsafe_allow_html=True)

    st.markdown("**Subcategoría**")
    _subcat_options = [None] + list(TournamentSubcategory)
    _subcat_labels  = {None: "⚪ Abierta"} | {s: s.label for s in TournamentSubcategory}
    _cur_subcat = t.subcategory if t else None
    t_subcategory = st.radio("Subcategoría", options=_subcat_options, format_func=lambda s: _subcat_labels[s],
                             index=_subcat_options.index(_cur_subcat) if _cur_subcat in _subcat_options else 0,
                             horizontal=True, label_visibility="collapsed")

    st.divider()
    _section_start("🏟️", "Pistas del torneo")
    if "t_courts_list" not in st.session_state:
        st.session_state["t_courts_list"] = [{"name": c.name} for c in t.courts] if t else [{"name": "Pista 1"}, {"name": "Pista 2"}]

    c_add, c_remove = st.columns([3, 1])
    with c_add:
        new_court_name = st.text_input("Nombre de la nueva pista", key="new_t_court_name", placeholder="Pista 3")
    with c_remove:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Añadir pista") and new_court_name.strip():
            st.session_state["t_courts_list"].append({"name": new_court_name.strip()})
            st.rerun()

    _tc_list = st.session_state["t_courts_list"]
    if _tc_list:
        _court_cols = st.columns(min(len(_tc_list), 4))
        for _ci, _ct in enumerate(_tc_list):
            with _court_cols[_ci % 4]:
                if st.button(f"🗑️ {_ct['name']}", key=f"del_court_{_ci}", help="Eliminar esta pista"):
                    st.session_state["t_courts_list"].pop(_ci)
                    st.rerun()
    else:
        st.warning("⚠️ Añade al menos una pista.")

    st.divider()
    _section_start("⏱️", "Parámetros de tiempo")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        t_match_dur = st.number_input("Duración del partido (min)", min_value=30, max_value=180, step=15, value=t.match_duration_minutes if t else 60)
        t_rest = st.number_input("Descanso mínimo entre partidos (min)", min_value=0, max_value=120, step=5, value=t.rest_between_matches_min if t else 15)
    with col_t2:
        t_day_start = st.time_input("Hora de inicio del día", value=t.day_start_time if t else _dt_mod.time(9, 0))
        t_day_end   = st.time_input("Hora de fin del día",    value=t.day_end_time   if t else _dt_mod.time(22, 0))
    with col_t3:
        t_group_size   = st.number_input("Parejas por grupo", min_value=3, max_value=8, value=t.group_size if t else 4) if t_format in (TournamentFormat.GROUPS, TournamentFormat.GROUPS_BRACKET) else 4
        t_bracket_size = st.selectbox("Tamaño del cuadro", [4, 8, 16], index=[4, 8, 16].index(t.bracket_size) if t else 1) if t_format in (TournamentFormat.BRACKET, TournamentFormat.GROUPS_BRACKET) else 8
        t_third_place  = st.checkbox("Partido 3er/4º puesto", value=t.third_place_match if t else False) if t_format in (TournamentFormat.BRACKET, TournamentFormat.GROUPS_BRACKET) else False
        t_qualifiers   = st.number_input("Clasificados por grupo al cuadro", min_value=1, max_value=4, value=t.groups_qualifiers if t else 2) if t_format == TournamentFormat.GROUPS_BRACKET else 2

    st.divider()
    if st.button("💾 Guardar y continuar →", type="primary", use_container_width=True):
        _courts_obj = [TournamentCourt(id=f"tc_{i}", name=c["name"]) for i, c in enumerate(st.session_state["t_courts_list"])]
        _pairs_keep = t.pairs if t else []
        new_t = TournamentConfig(
            id=t.id if t else str(__import__("uuid").uuid4()),
            name=t_name, category=t_category, subcategory=t_subcategory,
            is_top=t_is_top, prize=t_prize, location=t_location,
            start_date=t_start, end_date=t_end, courts=_courts_obj, pairs=_pairs_keep,
            format=t_format, match_duration_minutes=t_match_dur, rest_between_matches_min=t_rest,
            day_start_time=t_day_start, day_end_time=t_day_end,
            group_size=t_group_size, bracket_size=t_bracket_size,
            third_place_match=t_third_place, groups_qualifiers=t_qualifiers,
            groups=[], matches=[],
        )
        st.session_state["tournament"] = new_t
        st.success("✅ Configuración guardada.")
        st.session_state["_nav_page"] = "t_pairs"
        st.rerun()

    _t_nav_buttons(1)


# ---------------------------------------------------------------------------
# TORNEO — PASO 2: Parejas
# ---------------------------------------------------------------------------

elif page == "t_pairs":
    _t_header(2, "Añadir parejas", "Registra las parejas participantes del torneo")
    t = st.session_state.get("tournament")
    if not t:
        st.warning("⚠️ Primero configura el torneo.")
        if st.button("← Ir a Configuración"): st.session_state["_nav_page"] = "t_config"; st.rerun()
        st.stop()

    st.info(f"💡 Torneo: **{t.name}** · {len(t.pairs)} parejas inscritas · Formato: **{t.format.value}**")

    _section_start("👥", "Añadir parejas")
    pair_tab_a, pair_tab_b = st.tabs(["📝 Añadir manualmente", "📂 Importar CSV"])

    with pair_tab_a:
        pa1, pa2, pa3 = st.columns(3)
        with pa1:
            new_pair_name = st.text_input("Nombre de la pareja", placeholder="García / López", key="tnp_name")
            new_pair_seed = st.number_input("Cabeza de serie (0 = ninguna)", min_value=0, max_value=99, value=0, key="tnp_seed")
        with pa2:
            new_p1_name  = st.text_input("Jugador 1", placeholder="Carlos García", key="tnp_p1")
            new_p1_phone = st.text_input("Teléfono J1", placeholder="+34 600 000 000", key="tnp_p1ph")
        with pa3:
            new_p2_name  = st.text_input("Jugador 2", placeholder="Marta López", key="tnp_p2")
            new_p2_phone = st.text_input("Teléfono J2", placeholder="+34 600 000 001", key="tnp_p2ph")

        if st.button("➕ Añadir pareja", type="primary"):
            if new_pair_name.strip() and new_p1_name.strip() and new_p2_name.strip():
                new_pair = TournamentPair(
                    name=new_pair_name.strip(),
                    seed=new_pair_seed if new_pair_seed > 0 else None,
                    player_1=TournamentPlayer(name=new_p1_name.strip(), phone=new_p1_phone.strip() or None),
                    player_2=TournamentPlayer(name=new_p2_name.strip(), phone=new_p2_phone.strip() or None),
                )
                t.pairs.append(new_pair)
                t.groups = []; t.matches = []
                st.success(f"✅ '{new_pair.display_name}' añadida.")
                st.rerun()
            else:
                st.error("Rellena nombre de pareja y los dos jugadores.")

    with pair_tab_b:
        _sample_csv = "pair_name,player1_name,player2_name,player1_phone,player2_phone,seed\nGarcía / López,Carlos García,Marta López,+34600000001,+34600000002,1\nRuiz / Martín,Ana Ruiz,Luis Martín,,,\n"
        st.download_button("⬇️ Descargar plantilla CSV", _sample_csv, "plantilla_parejas.csv", "text/csv")
        csv_upload = st.file_uploader("Subir CSV de parejas", type=["csv"], key="t_csv_pairs")
        if csv_upload:
            try:
                _df_pairs = pd.read_csv(csv_upload)
                missing = {"pair_name", "player1_name", "player2_name"} - set(_df_pairs.columns)
                if missing:
                    st.error(f"Faltan columnas: {', '.join(missing)}")
                else:
                    new_pairs_csv = []
                    for _, row in _df_pairs.iterrows():
                        if pd.isna(row["pair_name"]) or not str(row["pair_name"]).strip(): continue
                        _seed_val = int(row["seed"]) if "seed" in row and not pd.isna(row.get("seed", float("nan"))) and str(row.get("seed","")).strip() else None
                        new_pairs_csv.append(TournamentPair(
                            name=str(row["pair_name"]).strip(), seed=_seed_val,
                            player_1=TournamentPlayer(name=str(row["player1_name"]).strip(), phone=str(row.get("player1_phone","")).strip() or None),
                            player_2=TournamentPlayer(name=str(row["player2_name"]).strip(), phone=str(row.get("player2_phone","")).strip() or None),
                        ))
                    if st.button(f"✅ Importar {len(new_pairs_csv)} parejas", type="primary"):
                        t.pairs.extend(new_pairs_csv)
                        t.groups = []; t.matches = []
                        st.success(f"✅ {len(new_pairs_csv)} parejas importadas."); st.rerun()
            except Exception as _csv_err:
                st.error(f"Error: {_csv_err}")

    st.divider()
    if t.pairs:
        _section_start("📋", f"Parejas inscritas ({len(t.pairs)})")
        _rows_pairs = [{"#": _pi+1, "Pareja": _pp.display_name,
                        "Jugador 1": _pp.player_1.full_name, "📱": _pp.player_1.phone or "—",
                        "Jugador 2": _pp.player_2.full_name, "📱 ": _pp.player_2.phone or "—",
                        "Cabeza serie": f"#{_pp.seed}" if _pp.seed else "—"}
                       for _pi, _pp in enumerate(t.pairs)]
        st.dataframe(_rows_pairs, use_container_width=True, hide_index=True)
        if st.button("🗑️ Vaciar lista de parejas", type="secondary"):
            t.pairs = []; t.groups = []; t.matches = []; st.rerun()
    else:
        _empty_state("👥", "Sin parejas", "Añade las parejas del torneo manualmente o importa un CSV.")

    _t_nav_buttons(2)


# ---------------------------------------------------------------------------
# TORNEO — PASO 3: Generar estructura
# ---------------------------------------------------------------------------

elif page == "t_generate":
    _t_header(3, "Generar estructura", "Crea grupos y cuadro eliminatorio automáticamente")
    t = st.session_state.get("tournament")
    if not t:
        st.warning("⚠️ Primero configura el torneo.")
        if st.button("← Configurar torneo"): st.session_state["_nav_page"] = "t_config"; st.rerun()
        st.stop()
    if not t.pairs:
        st.warning("⚠️ Añade las parejas antes de generar la estructura.")
        if st.button("← Añadir parejas"): st.session_state["_nav_page"] = "t_pairs"; st.rerun()
        st.stop()

    n_pairs = len(t.pairs)
    _section_start("🎯", "Previsión del torneo")

    if t.format == TournamentFormat.GROUPS:
        from math import comb as _comb
        n_groups = max(1, -(-n_pairs // t.group_size))
        total = n_groups * _comb(t.group_size, 2)
        c1, c2, c3 = st.columns(3)
        c1.metric("Grupos", n_groups); c2.metric("Parejas por grupo", t.group_size); c3.metric("Partidos estimados", total)
    elif t.format == TournamentFormat.BRACKET:
        bs = max(4, min(t.bracket_size, 1 << (n_pairs.bit_length()-1) if n_pairs >= 2 else 4))
        st.metric("Parejas en el cuadro", bs)
    elif t.format == TournamentFormat.GROUPS_BRACKET:
        n_groups = max(1, -(-n_pairs // t.group_size))
        q = n_groups * t.groups_qualifiers
        st.info(f"**{n_groups} grupos** → {t.groups_qualifiers} clasificados cada uno → **{q} al cuadro**")

    st.divider()
    if st.button("⚡ Generar estructura del torneo", type="primary", use_container_width=True):
        with st.spinner("Generando..."):
            t_gen = generate_tournament_structure(t)
        st.session_state["tournament"] = t_gen
        _summ = _t_summary(t_gen)
        st.success(f"✅ {_summ['n_groups']} grupos · {_summ['total_matches']} partidos generados")
        st.rerun()

    if t.groups:
        st.divider()
        _section_start("📋", "Grupos")
        _gcols = st.columns(min(len(t.groups), 4))
        for _gi, _grp in enumerate(t.groups):
            with _gcols[_gi % 4]:
                st.markdown(f"**{_grp.name}**")
                for _pp in _grp.pairs:
                    _seed_txt = f" 🏅#{_pp.seed}" if _pp.seed else ""
                    st.markdown(f"• {_pp.display_name}{_seed_txt}")

    if t.matches:
        st.divider()
        _section_start("📊", "Partidos generados")
        for _rnd in sorted(set(m.round for m in t.matches), key=lambda r: r.order):
            _rnd_matches = [m for m in t.matches if m.round == _rnd]
            with st.expander(f"**{_rnd.display}** — {len(_rnd_matches)} partidos", expanded=True):
                st.dataframe([{
                    "Partido": m.match_number,
                    "Grupo": next((g.name for g in t.groups if g.id == m.group_id), "") if m.group_id else "",
                    "Pareja 1": m.p1_display, "Pareja 2": m.p2_display,
                } for m in _rnd_matches], use_container_width=True, hide_index=True)

    _t_nav_buttons(3)


# ---------------------------------------------------------------------------
# TORNEO — PASO 4: Horarios
# ---------------------------------------------------------------------------

elif page == "t_schedule":
    import datetime as _dt_mod
    _t_header(4, "Asignar horarios", "Planificación automática de todos los partidos")
    t = st.session_state.get("tournament")
    if not t or not t.matches:
        st.warning("⚠️ Primero genera la estructura del torneo.")
        if st.button("← Generar estructura"): st.session_state["_nav_page"] = "t_generate"; st.rerun()
        st.stop()

    _section_start("🗓️", "Planificación automática")
    col_btn, col_sum = st.columns([1, 2])
    with col_btn:
        if st.button("🕐 Asignar horarios automáticamente", type="primary", use_container_width=True):
            with st.spinner("Planificando..."):
                t_sched = schedule_tournament(t)
            st.session_state["tournament"] = t_sched
            _ss = tournament_schedule_summary(t_sched)
            if _ss["conflicts"] == 0:
                st.success(f"✅ {_ss['scheduled']} partidos programados · {_ss['first_match']} → {_ss['last_match']}")
            else:
                st.warning(f"⚠️ {_ss['scheduled']} programados, {_ss['conflicts']} conflictos. Amplía el horario o añade pistas.")
            st.rerun()

    with col_sum:
        if any(m.status == TMatchStatus.SCHEDULED for m in t.matches):
            _ss2 = tournament_schedule_summary(t)
            _sm1, _sm2, _sm3 = st.columns(3)
            _sm1.metric("✅ Programados", _ss2["scheduled"])
            _sm2.metric("❌ Conflictos", _ss2["conflicts"])
            _sm3.metric("🏟️ Pistas usadas", len(_ss2["courts_used"]))
            if _ss2["first_match"]: st.caption(f"🕘 Inicio: **{_ss2['first_match']}**")
            if _ss2["last_match"]:  st.caption(f"🏁 Fin: **{_ss2['last_match']}**")

    if any(m.status == TMatchStatus.SCHEDULED for m in t.matches):
        st.divider()
        _section_start("📅", "Calendario del torneo")
        _days_in_t = sorted({m.match_date for m in t.matches if m.match_date})
        for _d in _days_in_t:
            _day_matches = sorted([m for m in t.matches if m.match_date == _d],
                                  key=lambda m: (m.start_time or _dt_mod.time(0,0), m.round.order))
            st.markdown(f'<div style="font-weight:700;font-size:1rem;color:#0b1a2b;margin:.8rem 0 .3rem">📅 {_d.strftime("%A %d/%m/%Y").capitalize()}</div>', unsafe_allow_html=True)
            st.dataframe([{
                "Estado": {TMatchStatus.SCHEDULED:"✅", TMatchStatus.CONFLICT:"❌", TMatchStatus.PENDING:"⏳"}.get(m.status,""),
                "Hora":   m.start_time.strftime("%H:%M") if m.start_time else "—",
                "Fin":    m.end_time.strftime("%H:%M")   if m.end_time   else "—",
                "Pista":  m.court.name if m.court else "—",
                "Ronda":  m.round_display,
                "Grupo":  next((g.name for g in t.groups if g.id == m.group_id), "") if m.group_id else "",
                "Pareja 1": m.p1_display, "Pareja 2": m.p2_display,
            } for m in _day_matches], use_container_width=True, hide_index=True)

    _t_nav_buttons(4)


# ---------------------------------------------------------------------------
# TORNEO — PASO 5: Exportar
# ---------------------------------------------------------------------------

elif page == "t_export":
    _t_header(5, "Exportar", "Descarga el Excel completo del torneo")
    t = st.session_state.get("tournament")
    if not t or not t.matches:
        st.warning("⚠️ Genera la estructura y asigna horarios antes de exportar.")
        if st.button("← Asignar horarios"): st.session_state["_nav_page"] = "t_schedule"; st.rerun()
        st.stop()

    import datetime as _dt_mod
    _section_start("📤", "Exportar calendario del torneo")

    col_xe1, col_xe2 = st.columns(2)
    with col_xe1:
        st.markdown("**Excel del torneo**")
        if st.button("📊 Generar Excel del torneo", type="primary"):
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
            import io as _io

            _wb = openpyxl.Workbook(); _wb.remove(_wb.active)
            _hdr_fill = PatternFill("solid", fgColor="1F4E79")
            _sch_fill = PatternFill("solid", fgColor="C6EFCE")
            _cfl_fill = PatternFill("solid", fgColor="FFC7CE")
            _odd_fill = PatternFill("solid", fgColor="F2F2F2")
            _evn_fill = PatternFill("solid", fgColor="FFFFFF")
            _thin_s   = Side(style="thin", color="CCCCCC")
            _border   = Border(left=_thin_s, right=_thin_s, top=_thin_s, bottom=_thin_s)

            def _hcell(ws, r, c, val):
                cell = ws.cell(row=r, column=c, value=val)
                cell.font = Font(bold=True, color="FFFFFF", size=11)
                cell.fill = _hdr_fill
                cell.border = _border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                return cell

            # Hoja 1: Todos los partidos
            _ws_all = _wb.create_sheet("Calendario")
            _hdrs = ["Fecha","Hora","Fin","Pista","Ronda","Grupo","Pareja 1","Pareja 2","Estado"]
            for _ci, _h in enumerate(_hdrs, 1): _hcell(_ws_all, 1, _ci, _h)

            for _ri, _m in enumerate(sorted(t.matches, key=lambda m: (
                m.match_date or _dt_mod.date.max,
                m.start_time or _dt_mod.time(0,0),
                m.round.order,
            )), start=2):
                _bg = _sch_fill if _m.status == TMatchStatus.SCHEDULED else (_cfl_fill if _m.status == TMatchStatus.CONFLICT else (_odd_fill if _ri%2 else _evn_fill))
                _vals = [
                    _m.match_date.strftime("%d/%m/%Y") if _m.match_date else "",
                    _m.start_time.strftime("%H:%M")    if _m.start_time  else "",
                    _m.end_time.strftime("%H:%M")      if _m.end_time    else "",
                    _m.court.name if _m.court else "",
                    _m.round_display,
                    next((g.name for g in t.groups if g.id == _m.group_id), "") if _m.group_id else "",
                    _m.p1_display, _m.p2_display, _m.status.value,
                ]
                for _ci, _v in enumerate(_vals, 1):
                    _cell = _ws_all.cell(row=_ri, column=_ci, value=_v)
                    _cell.fill = _bg; _cell.border = _border
                    _cell.font = Font(size=10)
                    _cell.alignment = Alignment(horizontal="left", vertical="center")

            for _col in _ws_all.columns:
                _max = max((len(str(cell.value or "")) for cell in _col), default=8)
                _ws_all.column_dimensions[get_column_letter(_col[0].column)].width = min(_max+4, 40)
            _ws_all.freeze_panes = "A2"; _ws_all.auto_filter.ref = _ws_all.dimensions

            # Hoja 2: Resumen
            _ws_r = _wb.create_sheet("Resumen")
            _cat_txt = t.category.label if t.category else "—"
            _sub_txt = t.subcategory.label if t.subcategory else "Abierta"
            _r_data = [
                ("Torneo",       t.name),
                ("TOP",          "⭐ SÍ" if t.is_top else "No"),
                ("Categoría",    _cat_txt),
                ("Subcategoría", _sub_txt),
                ("Sede",         t.location or "—"),
                ("Premio",       t.prize or "—"),
                ("Formato",      t.format.value),
                ("Inicio",       t.start_date.strftime("%d/%m/%Y")),
                ("Fin",          t.end_date.strftime("%d/%m/%Y")),
                ("Parejas",      len(t.pairs)),
                ("Grupos",       len(t.groups)),
                ("Total partidos", len(t.matches)),
                ("Programados",  t.scheduled_count),
                ("Conflictos",   t.conflict_count),
            ]
            for _ri, (k, v) in enumerate(_r_data, 1):
                _ws_r.cell(row=_ri, column=1, value=k).font = Font(bold=True)
                _ws_r.cell(row=_ri, column=2, value=str(v))
            _ws_r.column_dimensions["A"].width = 22; _ws_r.column_dimensions["B"].width = 30

            _buf = _io.BytesIO(); _wb.save(_buf); _buf.seek(0)
            _fname = f"torneo_{t.name.replace(' ','_')}_{t.start_date}.xlsx"
            st.download_button("⬇️ Descargar Excel del torneo", data=_buf.getvalue(),
                               file_name=_fname,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dl_tournament_xlsx")
            st.success("✅ Excel generado.")

    with col_xe2:
        st.markdown("**Resumen rápido**")
        _summ_exp = _t_summary(t)
        _m1, _m2, _m3 = st.columns(3)
        _m1.metric("Total partidos", _summ_exp["total_matches"])
        _m2.metric("Grupos",         _summ_exp["n_groups"])
        _m3.metric("Parejas",        _summ_exp["n_pairs"])
        st.json(_summ_exp["matches_by_round"])

    _t_nav_buttons(5)


# ---------------------------------------------------------------------------
# PÁGINA: Administración (solo superadmin, requiere DB)
# ---------------------------------------------------------------------------

elif page == "admin":
    _page_header("🛠️", "Administración", "Gestión de clubs y usuarios")

    if not _db_ok or _db is None:
        st.error("❌ Base de datos no configurada. Añade SUPABASE_URL y SUPABASE_KEY.")
        st.stop()

    if not is_superadmin():
        st.error("⛔ Solo el superadmin puede acceder a esta sección.")
        st.stop()

    tab_clubs, tab_users = st.tabs(["🏢 Clubs", "👤 Usuarios"])

    # ── Tab Clubs ──────────────────────────────────────────────────────────
    with tab_clubs:
        st.markdown("### Clubs registrados")
        _clubs_list = _db.list_clubs()
        if _clubs_list:
            _df_clubs = pd.DataFrame(_clubs_list)[["id", "name", "slug", "created_at"]]
            _df_clubs.columns = ["ID", "Nombre", "Slug", "Creado"]
            st.dataframe(_df_clubs, use_container_width=True, hide_index=True)
        else:
            st.info("No hay clubs registrados todavía.")

        st.markdown("---")
        st.markdown("#### ➕ Crear nuevo club")
        with st.form("form_create_club"):
            _new_club_name = st.text_input("Nombre del club", placeholder="Pádel Madrid Centro")
            _new_club_slug = st.text_input("Slug (URL-friendly)", placeholder="padel-madrid-centro")
            if st.form_submit_button("Crear club", type="primary"):
                if not _new_club_name or not _new_club_slug:
                    st.error("Rellena nombre y slug.")
                else:
                    try:
                        _created = _db.create_club(_new_club_name.strip(), _new_club_slug.strip())
                        st.success(f"✅ Club '{_created['name']}' creado (ID: {_created['id']})")
                        st.rerun()
                    except Exception as _ex:
                        st.error(f"Error al crear el club: {_ex}")

    # ── Tab Usuarios ───────────────────────────────────────────────────────
    with tab_users:
        from src.auth import hash_password as _hash_pw

        st.markdown("### Usuarios del sistema")
        _users_list = _db.list_users()
        if _users_list:
            _df_users = pd.DataFrame(_users_list)
            # Nunca mostrar el hash de contraseña
            _df_users = _df_users.drop(columns=["password_hash"], errors="ignore")
            st.dataframe(_df_users, use_container_width=True, hide_index=True)
        else:
            st.info("No hay usuarios registrados todavía.")

        st.markdown("---")
        st.markdown("#### ➕ Crear nuevo usuario")
        _clubs_for_select = _db.list_clubs()
        _club_map = {"(superadmin — sin club)": None}
        _club_map.update({c["name"]: c["id"] for c in _clubs_for_select})

        with st.form("form_create_user"):
            _nu_username    = st.text_input("Nombre de usuario", placeholder="club_admin_madrid")
            _nu_display     = st.text_input("Nombre para mostrar", placeholder="Admin Madrid")
            _nu_email       = st.text_input("Email (opcional)", placeholder="admin@padelmadrid.es")
            _nu_password    = st.text_input("Contraseña", type="password")
            _nu_role        = st.selectbox("Rol", ["club_admin", "superadmin"])
            _nu_club_label  = st.selectbox("Club", list(_club_map.keys()))
            _nu_club_id     = _club_map[_nu_club_label]

            if st.form_submit_button("Crear usuario", type="primary"):
                if not _nu_username or not _nu_password:
                    st.error("Usuario y contraseña son obligatorios.")
                else:
                    try:
                        _db.create_user(
                            username=_nu_username,
                            password_hash=_hash_pw(_nu_password),
                            role=_nu_role,
                            club_id=_nu_club_id,
                            display_name=_nu_display,
                            email=_nu_email,
                        )
                        st.success(f"✅ Usuario '{_nu_username}' creado.")
                        st.rerun()
                    except Exception as _ex:
                        st.error(f"Error al crear el usuario: {_ex}")

        st.markdown("---")
        st.markdown("#### 🔑 Cambiar contraseña")
        with st.form("form_change_pw"):
            _cp_user_labels = [u["username"] for u in (_users_list or [])]
            if _cp_user_labels:
                _cp_username = st.selectbox("Usuario", _cp_user_labels)
                _cp_new_pw   = st.text_input("Nueva contraseña", type="password")
                if st.form_submit_button("Cambiar contraseña"):
                    if not _cp_new_pw:
                        st.error("Introduce la nueva contraseña.")
                    else:
                        _cp_user_obj = next((u for u in _users_list if u["username"] == _cp_username), None)
                        if _cp_user_obj:
                            _db.update_user_password(_cp_user_obj["id"], _hash_pw(_cp_new_pw))
                            st.success(f"✅ Contraseña de '{_cp_username}' actualizada.")
            else:
                st.info("No hay usuarios para gestionar.")
