"""
Ranking Padel Automator — Interfaz Streamlit
"""
import re
import sys
import io
import uuid
from html import escape
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ═══════════════════════════════════════════════════════════════════
   RANKING PÁDEL AUTOMATOR — Design System v3
   ═══════════════════════════════════════════════════════════════════ */

/* ── BASE ───────────────────────────────────────────────────────── */
html, body, .stApp, .main,
button, input, textarea, select,
h1, h2, h3, h4, h5, h6, p, span, label, div {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
}
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

/* ══════════════════════════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: #07111d !important;
    border-right: 1px solid rgba(255,255,255,.07) !important;
}
/* Texto base del sidebar */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not([data-baseweb]),
[data-testid="stSidebar"] label { color: #94b8d8 !important; }
[data-testid="stSidebar"] hr   { border-color: rgba(255,255,255,.07) !important; margin: .6rem 0 !important; }

/* ─ Botones de navegación superior (Club, Admin, Logout) ─ */
[data-testid="stSidebar"] > div > div > div > [data-testid="stVerticalBlock"] > [data-testid="element-container"] button,
[data-testid="stSidebar"] button {
    border-radius: 10px !important;
    font-size: .84rem !important;
    font-weight: 600 !important;
    text-align: left !important;
    transition: all .18s cubic-bezier(.4,0,.2,1) !important;
    letter-spacing: .01em !important;
}
/* Secondary (default) */
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    background: rgba(255,255,255,.05) !important;
    color: #94b8d8 !important;
    border: 1px solid rgba(255,255,255,.09) !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background: rgba(0,200,83,.12) !important;
    border-color: rgba(0,200,83,.30) !important;
    color: #7fffc0 !important;
}
/* Primary (active page) */
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg,rgba(0,200,83,.25),rgba(0,168,107,.20)) !important;
    color: #7fffc0 !important;
    border: 1px solid rgba(0,200,83,.40) !important;
    font-weight: 700 !important;
    box-shadow: 0 0 0 0 rgba(0,200,83,0) !important;
}
[data-testid="stSidebar"] button[kind="primary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg,rgba(0,200,83,.35),rgba(0,168,107,.28)) !important;
    color: #b8ffd8 !important;
}
/* Logout */
[data-testid="stSidebar"] [data-key="btn_logout"] button {
    background: rgba(239,68,68,.10) !important;
    color: #fca5a5 !important;
    border-color: rgba(239,68,68,.22) !important;
}
[data-testid="stSidebar"] [data-key="btn_logout"] button:hover {
    background: rgba(239,68,68,.22) !important;
    color: #fecaca !important;
    border-color: rgba(239,68,68,.45) !important;
}

/* ─ Expanders RANKING / TORNEOS ─ */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,.03) !important;
    border: 1px solid rgba(255,255,255,.08) !important;
    border-radius: 12px !important;
    margin-bottom: 6px !important;
    overflow: hidden !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-size: .72rem !important;
    font-weight: 800 !important;
    letter-spacing: .14em !important;
    text-transform: uppercase !important;
    color: #4a7aa0 !important;
    padding: 12px 14px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    color: #94b8d8 !important;
    background: rgba(255,255,255,.04) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    color: #4a7aa0 !important;
    fill: #4a7aa0 !important;
    transition: color .15s !important;
}

/* ─ Step buttons inside expanders ─ */
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {
    gap: 1px !important;
    padding: 4px 8px 10px !important;
}
/* Pending step */
[data-testid="stSidebar"] [data-testid="stExpander"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: #4a7aa0 !important;
    font-size: .84rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    padding: 7px 10px !important;
    height: auto !important;
    min-height: 34px !important;
    line-height: 1.3 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] button[kind="secondary"]:hover,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stBaseButton-secondary"]:hover {
    background: rgba(148,184,216,.08) !important;
    color: #94b8d8 !important;
    border: none !important;
}
/* Active step */
[data-testid="stSidebar"] [data-testid="stExpander"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stBaseButton-primary"] {
    background: rgba(0,200,83,.14) !important;
    border: none !important;
    border-left: 3px solid #00c853 !important;
    border-radius: 0 8px 8px 0 !important;
    color: #7fffc0 !important;
    font-size: .84rem !important;
    font-weight: 700 !important;
    text-align: left !important;
    padding: 7px 10px 7px 9px !important;
    height: auto !important;
    min-height: 34px !important;
}

/* ══════════════════════════════════════════════════════════════════
   PÁGINA PRINCIPAL
   ══════════════════════════════════════════════════════════════════ */

/* ── Cabecera de página ─────────────────────────────────────────── */
.pp-page-title {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: .2rem 0 1.4rem 0;
    border-bottom: 2px solid #e8f0f8;
    margin-bottom: 2rem;
}
.pp-page-title .pp-icon {
    width: 52px; height: 52px;
    background: linear-gradient(135deg, #e8f8f0, #d0f2e4);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem; flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0,200,83,.18);
}
.pp-page-title .pp-text h1 {
    margin: 0;
    font-size: 1.7rem;
    font-weight: 800;
    color: #07111d;
    line-height: 1.15;
    letter-spacing: -.03em;
}
.pp-page-title .pp-text p {
    margin: .2rem 0 0 0;
    font-size: .87rem;
    color: #7f9ab5;
    font-weight: 400;
}

/* ── Tarjeta de sección ─────────────────────────────────────────── */
.pp-section {
    background: #fff;
    border: 1px solid #edf2fa;
    border-radius: 16px;
    padding: 1.5rem 1.8rem 1.3rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 1px 3px rgba(11,26,43,.04), 0 4px 20px rgba(11,26,43,.06);
}
.pp-section-title {
    display: flex;
    align-items: center;
    gap: .5rem;
    font-size: .68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .14em;
    color: #00843d;
    margin-bottom: 1.1rem;
    padding-bottom: .65rem;
    border-bottom: 1px solid #edf4ea;
}
.pp-section-title span { font-size: .95rem; }

/* ── Métricas ───────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #fff !important;
    border: 1px solid #edf2fa !important;
    border-radius: 14px !important;
    padding: 18px 22px !important;
    box-shadow: 0 1px 3px rgba(11,26,43,.04) !important;
    transition: box-shadow .2s, transform .2s !important;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 6px 20px rgba(11,26,43,.10) !important;
    transform: translateY(-2px) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    color: #07111d !important;
    letter-spacing: -.03em !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: .68rem !important;
    color: #7f9ab5 !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: .1em !important;
}

/* ── Botones principales ────────────────────────────────────────── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: .88rem !important;
    letter-spacing: .015em !important;
    transition: all .18s cubic-bezier(.4,0,.2,1) !important;
    padding: .5rem 1.3rem !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00c853 0%, #00897b 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 3px 14px rgba(0,200,83,.35) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 22px rgba(0,200,83,.45) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0) !important; }
.stButton > button[kind="secondary"] {
    border: 1.5px solid #dce8f5 !important;
    color: #1b3a58 !important;
    background: #fff !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #00c853 !important;
    color: #005a29 !important;
    background: rgba(0,200,83,.04) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stDownloadButton"] button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #1565c0, #0d47a1) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 3px 12px rgba(21,101,192,.32) !important;
    transition: all .18s !important;
}
[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 18px rgba(21,101,192,.42) !important;
}

/* ── Tabs ───────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    gap: 0;
    border-bottom: 2px solid #edf2fa;
    background: transparent;
    padding: 0 0 0 4px;
}
[data-testid="stTabs"] button[role="tab"] {
    border-radius: 8px 8px 0 0 !important;
    padding: 9px 22px !important;
    font-weight: 600 !important;
    font-size: .87rem !important;
    color: #7f9ab5 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all .15s !important;
    margin-bottom: -2px !important;
}
[data-testid="stTabs"] button[role="tab"]:hover { color: #1b3a58 !important; }
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00843d !important;
    background: transparent !important;
    border-bottom: 2px solid #00c853 !important;
    font-weight: 700 !important;
}

/* ── Expanders (contenido) ──────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #edf2fa !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: none !important;
    transition: box-shadow .15s !important;
}
[data-testid="stExpander"]:hover { box-shadow: 0 2px 12px rgba(11,26,43,.07) !important; }
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: #2d4a6a !important;
    font-size: .9rem !important;
    padding: .8rem 1.1rem !important;
    background: #fafcff !important;
}
[data-testid="stExpander"] summary:hover { background: #f0f6ff !important; }

/* ── Alertas ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border-width: 1.5px !important;
    font-size: .88rem !important;
}

/* ── DataFrames ─────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 8px rgba(11,26,43,.07) !important;
    border: 1px solid #edf2fa !important;
}

/* ── Inputs ─────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 10px !important;
    border-color: #dce8f5 !important;
    background: #fafcff !important;
    font-size: .9rem !important;
    transition: border-color .15s, box-shadow .15s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #00c853 !important;
    background: #fff !important;
    box-shadow: 0 0 0 3px rgba(0,200,83,.12) !important;
}
/* Labels */
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stSlider"] label,
[data-testid="stTimeInput"] label,
[data-testid="stDateInput"] label {
    font-size: .82rem !important;
    font-weight: 600 !important;
    color: #3d5a78 !important;
    letter-spacing: .01em !important;
}
/* Select/Dropdown */
[data-testid="stSelectbox"] > div > div {
    border-radius: 10px !important;
    border-color: #dce8f5 !important;
    background: #fafcff !important;
}
/* Number input */
[data-testid="stNumberInput"] button {
    border-radius: 6px !important;
}
/* Slider */
[data-baseweb="slider"] [role="slider"] {
    background: #00c853 !important;
    border-color: #00c853 !important;
    width: 18px !important; height: 18px !important;
    box-shadow: 0 0 0 4px rgba(0,200,83,.18) !important;
}
[data-baseweb="slider"] [data-testid="stSlider"] div[role="progressbar"] {
    background: #00c853 !important;
}

/* ── Progress ────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #00c853, #00897b) !important;
    border-radius: 6px !important;
}

/* ── File uploader ──────────────────────────────────────────────── */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #c8dff5 !important;
    border-radius: 14px !important;
    background: #f5f9ff !important;
    transition: all .2s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #00c853 !important;
    background: rgba(0,200,83,.03) !important;
}

/* ── Checkbox / Toggle ──────────────────────────────────────────── */
[data-testid="stCheckbox"] label,
[data-testid="stToggle"] label {
    font-size: .88rem !important;
    color: #2d4a6a !important;
    font-weight: 500 !important;
}

/* ── Divider ─────────────────────────────────────────────────────── */
hr { border-color: #edf2fa !important; }

/* ── BADGES ─────────────────────────────────────────────────────── */
.pp-badge-safe {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0,200,83,.12);
    color: #005a29 !important;
    border: 1px solid rgba(0,200,83,.28);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: .76rem; font-weight: 700; letter-spacing: .04em;
}
.pp-badge-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(239,68,68,.12);
    color: #b91c1c !important;
    border: 1px solid rgba(239,68,68,.28);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: .76rem; font-weight: 700; letter-spacing: .04em;
}
/* ── Sidebar stepper (legacy class) ─────────────────────────────── */
.pp-step { display:flex; align-items:center; gap:10px; padding:5px 10px; border-radius:9px; margin:2px 0; font-size:.84rem; }
.pp-step.done   { color:#7fffc0!important; }
.pp-step.active { color:#fff!important; font-weight:700; background:rgba(0,200,83,.18); }
.pp-step.todo   { color:#4a6a8a!important; }
.pp-step .pp-step-dot { width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.75rem;flex-shrink:0;font-weight:700; }
.pp-step.done .pp-step-dot   { background:#00c853;color:#fff; }
.pp-step.active .pp-step-dot { background:#fff;color:#07111d; }
.pp-step.todo .pp-step-dot   { background:#1e3a58;color:#4a6a8a; }

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
[data-testid="stExpander"] summary::before {
    content: ">";
    color: #7f9ab5;
    font-weight: 900;
    font-size: .78rem;
    margin-right: .5rem;
}
[data-testid="stExpander"] details[open] summary::before {
    content: "v";
}
[data-testid="stExpander"] summary > span > span:first-child,
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
}

/* Comercial polish: ocultar chrome de Streamlit y estabilizar navegación */
#MainMenu,
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="collapsedControl"],
.stDeployButton {
    visibility: hidden !important;
    display: none !important;
}
header[data-testid="stHeader"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
}
header[data-testid="stHeader"] * {
    display: none !important;
    visibility: hidden !important;
}
.stApp {
    background: #f0f4f8 !important;
}
.main .block-container {
    max-width: 1480px !important;
    padding-top: 3.2rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
}
[data-testid="stSidebar"] {
    min-width: 306px !important;
    max-width: 306px !important;
    background: #07121f !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: .22rem !important;
}
[data-testid="stSidebar"] button[kind="headerNoPadding"],
[data-testid="stSidebar"] [data-testid="stBaseButton-headerNoPadding"] {
    display: none !important;
    visibility: hidden !important;
}
/* ── Todos los botones del sidebar: base de enlace de navegación ─── */
[data-testid="stSidebar"] [data-testid="stButton"] button {
    width: 100% !important;
    height: 36px !important;
    min-height: 36px !important;
    justify-content: flex-start !important;
    text-align: left !important;
    border-radius: 7px !important;
    padding: 0 .9rem !important;
    box-shadow: none !important;
    transform: none !important;
    overflow: hidden !important;
    transition: background .13s, color .13s !important;
    font-size: .84rem !important;
    font-weight: 500 !important;
    letter-spacing: .005em !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button div[data-testid="stMarkdownContainer"] {
    width: 100% !important; text-align: left !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button p {
    white-space: nowrap !important; overflow: hidden !important;
    text-overflow: ellipsis !important; text-align: left !important;
    width: 100% !important; margin: 0 !important;
}
/* Inactive nav item — completamente plano, sin forma de botón */
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    color: #7a9ec0 !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background: rgba(255,255,255,.06) !important;
    color: #cce4f6 !important;
    border: none !important;
}
/* Active nav item — acento izquierdo verde, sin relleno lleno */
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: rgba(0,200,83,.13) !important;
    border: none !important;
    border-left: 3px solid #00c853 !important;
    border-radius: 0 7px 7px 0 !important;
    color: #6effc0 !important;
    font-weight: 700 !important;
    padding-left: calc(.9rem - 3px) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] label {
    color: #7f9ab5 !important;
    font-size: .72rem !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,.06) !important;
    border: 1px solid rgba(255,255,255,.10) !important;
    border-radius: 8px !important;
    color: #e8f4ff !important;
}
.pp-brand {
    padding: 1.35rem 1rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,.08);
    margin-bottom: .75rem;
}
.pp-brand-row {
    display: flex;
    align-items: center;
    gap: .75rem;
}
.pp-brand-mark {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    background: linear-gradient(135deg, #00c853 0%, #007a73 100%);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: .9rem;
    letter-spacing: -.02em;
    box-shadow: 0 4px 16px rgba(0,200,83,.30), inset 0 1px 0 rgba(255,255,255,.25);
    flex-shrink: 0;
}
.pp-brand-title {
    color: #f6fbff;
    font-weight: 850;
    font-size: 1.05rem;
    line-height: 1;
}
.pp-brand-subtitle {
    color: #6f8ca8;
    font-size: .69rem;
    letter-spacing: .11em;
    text-transform: uppercase;
    margin-top: .2rem;
}
.pp-nav-section {
    color: #2e5068;
    font-size: .6rem;
    letter-spacing: .18em;
    text-transform: uppercase;
    font-weight: 800;
    padding: 1.1rem .9rem .55rem;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,.035) !important;
    border: 1px solid rgba(255,255,255,.08) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    margin: .25rem .12rem .5rem !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background: transparent !important;
    color: #94b8d8 !important;
    border-radius: 7px !important;
    padding: .65rem .9rem !important;
    font-size: .83rem !important;
    font-weight: 600 !important;
    letter-spacing: .01em !important;
    text-transform: none !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary::before {
    content: ">";
    color: #8fb0cd;
    font-weight: 900;
    font-size: .78rem;
    margin-right: .5rem;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary::before {
    content: "v";
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary > span > span:first-child,
[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
    background: rgba(255,255,255,.075) !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
    color: #8fb0cd !important;
    fill: #8fb0cd !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {
    gap: .3rem !important;
    padding: .35rem .35rem .55rem !important;
}
.pp-flow-meta {
    color: #7592ae;
    font-size: .72rem;
    line-height: 1.35;
    padding: .45rem .7rem .35rem;
}
.pp-flow-progress {
    height: 5px;
    background: rgba(255,255,255,.08);
    border-radius: 999px;
    margin: .15rem .7rem .55rem;
    overflow: hidden;
}
.pp-flow-progress > span {
    display: block;
    height: 100%;
    background: linear-gradient(90deg,#00c47a,#0aa3a3);
    border-radius: 999px;
}
.pp-step-help {
    background: rgba(0,196,122,.10);
    border: 1px solid rgba(0,196,122,.18);
    color: #bff3df;
    border-radius: 8px;
    padding: .6rem .7rem;
    font-size: .76rem;
    line-height: 1.38;
    margin: .4rem .35rem .65rem;
}
.pp-step-help strong {
    display: block;
    color: #ffffff;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    margin-bottom: .18rem;
}
.pp-flow-spacer {
    height: .35rem;
}
.pp-user-card {
    margin: .3rem .5rem .6rem;
    padding: .7rem .85rem;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.07);
    background: rgba(255,255,255,.04);
}
.pp-user-name {
    color: #ddeeff;
    font-weight: 700;
    font-size: .85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.pp-user-meta {
    color: #4a7090;
    font-size: .72rem;
    margin-top: .15rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.pp-empty-club {
    background: transparent;
    border: none !important;
    border-left: 2px solid rgba(245,158,11,.5) !important;
    border-radius: 0;
    color: #7a6040;
    font-size: .74rem;
    line-height: 1.35;
    margin: .2rem .4rem .4rem 1rem !important;
    padding: .3rem .7rem !important;
}
.pp-sidebar-footer {
    padding: .6rem .9rem 1.2rem;
    margin-top: .4rem;
    border-top: 1px solid rgba(255,255,255,.06);
}
.pp-mode-pill {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    border-radius: 6px;
    border: 1px solid rgba(0,200,83,.20);
    padding: .3rem .7rem;
    color: #4a9a72;
    background: rgba(0,200,83,.07);
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
}
.pp-page-title {
    border-bottom: 1px solid #dde8f4 !important;
}
.pp-page-title .pp-icon {
    border-radius: 8px !important;
    box-shadow: none !important;
}
.pp-section-title {
    color: #0d7d55 !important;
}
/* ── Hero banner ─────────────────────────────────────────────────── */
.pp-hero {
    background: linear-gradient(135deg, #07111d 0%, #0a1f35 60%, #0d2a47 100%);
    border-radius: 16px;
    padding: 2.2rem 2.4rem 2rem;
    margin-bottom: 1.6rem;
    position: relative;
    overflow: hidden;
}
.pp-hero::after {
    content: "";
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(0,200,83,.18) 0%, transparent 70%);
    pointer-events: none;
}
.pp-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    color: #00c853;
    font-size: .7rem;
    font-weight: 800;
    letter-spacing: .14em;
    text-transform: uppercase;
    margin-bottom: .7rem;
    background: rgba(0,200,83,.12);
    border: 1px solid rgba(0,200,83,.25);
    border-radius: 20px;
    padding: .2rem .75rem;
}
.pp-hero h1 {
    color: #ffffff;
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.15;
    margin: 0;
    letter-spacing: -.02em;
}
.pp-hero p {
    margin: .65rem 0 0;
    max-width: 680px;
    color: rgba(255,255,255,.6);
    font-size: .95rem;
    line-height: 1.55;
}

/* ── KPI grid ─────────────────────────────────────────────────────── */
.pp-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
    margin: 0 0 1.4rem;
}
.pp-kpi-card {
    background: #fff;
    border: 1px solid #e2eaf4;
    border-radius: 12px;
    padding: 1.1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(11,26,43,.05), 0 4px 16px rgba(11,26,43,.04);
    transition: transform .15s, box-shadow .15s;
}
.pp-kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(11,26,43,.10);
}
.pp-kpi-label {
    color: #7088a0;
    font-size: .68rem;
    font-weight: 800;
    letter-spacing: .1em;
    text-transform: uppercase;
    margin-bottom: .4rem;
}
.pp-kpi-value {
    color: #07111d;
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -.03em;
}
.pp-kpi-note {
    color: #94a8be;
    font-size: .74rem;
    margin-top: .35rem;
}

/* ── Info / action cards ─────────────────────────────────────────── */
.pp-two-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
    margin: 0 0 1.4rem;
}
.pp-action-card,
.pp-onboarding-card {
    background: #fff;
    border: 1px solid #e2eaf4;
    border-radius: 12px;
    padding: 1.2rem 1.3rem;
    box-shadow: 0 1px 3px rgba(11,26,43,.04);
    transition: transform .15s, box-shadow .15s;
}
.pp-action-card:hover,
.pp-onboarding-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(11,26,43,.09);
    border-color: #c5d8ed;
}
.pp-card-title {
    color: #07111d;
    font-weight: 700;
    font-size: .95rem;
    margin-bottom: .4rem;
    display: flex;
    align-items: center;
    gap: .4rem;
}
.pp-card-text {
    color: #5d7a96;
    font-size: .86rem;
    line-height: 1.5;
}

@media (max-width: 900px) {
    .main .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .pp-kpi-grid, .pp-two-grid { grid-template-columns: 1fr; }
    .pp-hero h1 { font-size: 1.5rem; }
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


def _dashboard_hero(title: str, subtitle: str, eyebrow: str = "Panel del club") -> None:
    st.markdown(
        f'<section class="pp-hero">'
        f'<div class="pp-eyebrow">{escape(eyebrow)}</div>'
        f'<h1>{escape(title)}</h1>'
        f'<p>{escape(subtitle)}</p>'
        f'</section>',
        unsafe_allow_html=True,
    )


_KPI_COLORS = ["#00c853", "#1565c0", "#7b1fa2", "#e65100"]
_KPI_BG     = ["rgba(0,200,83,.08)", "rgba(21,101,192,.08)", "rgba(123,31,162,.08)", "rgba(230,81,0,.08)"]

def _kpi_grid(cards: list[tuple[str, str, str]]) -> None:
    html = ['<div class="pp-kpi-grid">']
    for i, (label, value, note) in enumerate(cards):
        c  = _KPI_COLORS[i % len(_KPI_COLORS)]
        bg = _KPI_BG[i % len(_KPI_BG)]
        html.append(
            f'<div class="pp-kpi-card" style="border-top:3px solid {c}">'
            f'<div class="pp-kpi-label">{escape(label)}</div>'
            f'<div class="pp-kpi-value" style="color:{c}">{escape(str(value))}</div>'
            f'<div class="pp-kpi-note">{escape(note)}</div>'
            '</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


_STEP_ICONS = ["🏢", "👤", "🎾", "🚀"]

def _info_grid(cards: list[tuple[str, str]]) -> None:
    html = ['<div class="pp-two-grid">']
    for i, (title, text) in enumerate(cards):
        icon = _STEP_ICONS[i % len(_STEP_ICONS)]
        # Extract number prefix like "1. " if present
        clean_title = title
        num_badge = ""
        import re as _re
        m = _re.match(r'^(\d+)\.\s*(.*)', title)
        if m:
            num_badge = (
                f'<span style="width:22px;height:22px;border-radius:50%;'
                f'background:#07111d;color:#fff;font-size:.7rem;font-weight:800;'
                f'display:inline-flex;align-items:center;justify-content:center;flex-shrink:0">'
                f'{m.group(1)}</span>'
            )
            clean_title = m.group(2)
        html.append(
            '<div class="pp-action-card">'
            f'<div class="pp-card-title">{num_badge}{escape(clean_title)}</div>'
            f'<div class="pp-card-text">{escape(text)}</div>'
            '</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _nav_to(target: str) -> None:
    st.session_state["_nav_page"] = target
    st.rerun()


def _sidebar_button(label: str, target: str, current_page: str, key: str) -> None:
    if st.sidebar.button(
        label,
        key=key,
        use_container_width=True,
        type="primary" if current_page == target else "secondary",
    ):
        _nav_to(target)


def _sidebar_workflow(title: str, steps: list[tuple[str, str, str, bool]], current_page: str, key_prefix: str, expanded: bool) -> None:
    done_count = sum(1 for _, _, _, done in steps if done)
    pct_done = int((done_count / max(len(steps), 1)) * 100)
    current_hint = next((hint for step_key, _, hint, _ in steps if step_key == current_page), "")
    open_key = f"_{key_prefix}_workflow_open"
    if open_key not in st.session_state:
        st.session_state[open_key] = expanded
    if expanded:
        st.session_state[open_key] = True

    is_open = bool(st.session_state.get(open_key))
    header_marker = "v" if is_open else ">"
    if st.sidebar.button(
        f"{header_marker}  {title} · {done_count}/{len(steps)} pasos",
        key=f"{key_prefix}_workflow_toggle",
        use_container_width=True,
        type="primary" if expanded else "secondary",
    ):
        st.session_state[open_key] = not is_open
        st.rerun()

    if is_open:
        st.sidebar.markdown(
            '<div class="pp-flow-meta">Completa este flujo de arriba abajo. El panel se mantiene abierto mientras trabajas en sus pasos.</div>'
            f'<div class="pp-flow-progress"><span style="width:{pct_done}%"></span></div>',
            unsafe_allow_html=True,
        )
        for idx, (step_key, label, hint, done) in enumerate(steps, 1):
            marker = "OK" if done else f"{idx:02d}"
            button_label = f"{marker}  {label}"
            if st.sidebar.button(
                button_label,
                key=f"{key_prefix}_{step_key}",
                use_container_width=True,
                type="primary" if current_page == step_key else "secondary",
            ):
                _nav_to(step_key)
        if current_hint:
            st.sidebar.markdown(
                f'<div class="pp-step-help"><strong>Paso actual</strong>{escape(current_hint)}</div>',
                unsafe_allow_html=True,
            )
    st.sidebar.markdown('<div class="pp-flow-spacer"></div>', unsafe_allow_html=True)


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
    is_superadmin, current_club_id, current_club_name, logout, restore_session_from_cookie,
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


def _reset_club_runtime_state() -> None:
    """
    Limpia el estado en memoria que depende del club activo.
    Se usa al cambiar de club en modo superadmin.
    """
    st.session_state["groups"] = []
    st.session_state["courts"] = []
    st.session_state["bookings"] = []
    st.session_state["matches"] = []
    st.session_state["schedule_result"] = None
    st.session_state["phase"] = None
    st.session_state["data_loaded"] = False
    st.session_state["matches_generated"] = False
    st.session_state["matches_scheduled"] = False
    st.session_state["db_phase_id"] = None
    st.session_state["_db_phase_loaded"] = False
    st.session_state["tournament"] = None
    st.session_state["db_tournament_id"] = None
    st.session_state["_db_tournament_loaded"] = False
    st.session_state["_t_config_divisions_source_id"] = None
    st.session_state.pop("t_config_divisions", None)
    st.session_state.pop("t_courts_list", None)
    st.session_state.pop("schedule_violations", None)
    st.session_state.pop("_filter_cache_key", None)
    st.session_state.pop("_group_names", None)
    st.session_state.pop("_pair_names", None)
    st.session_state.pop("_match_id_to_obj", None)
    st.session_state.pop("_court_name_to_obj", None)
    # Estado/cache de integración Syltek por club
    st.session_state.pop("syltek_logged_in", None)
    st.session_state.pop("syltek_courts", None)
    st.session_state.pop("syltek_publish_results", None)
    st.session_state.pop("syltek_credentials", None)
    st.session_state.pop("syl_url", None)
    st.session_state.pop("syl_user", None)
    st.session_state.pop("syl_pass", None)
    st.session_state.pop("syl_imp_url", None)
    st.session_state.pop("syl_imp_user", None)
    st.session_state.pop("syl_imp_pass", None)
    for _k in list(st.session_state.keys()):
        if _k.startswith("court_id_"):
            st.session_state.pop(_k, None)


_DEFAULT_SYLTEK_LOGIN_URL = "https://padelplus.syltek.com/system/account/login"


def _club_settings_dict(club_row: dict | None) -> dict:
    if not club_row:
        return {}
    _raw = club_row.get("settings")
    return _raw if isinstance(_raw, dict) else {}


def _default_syltek_url(club_row: dict | None) -> str:
    _cfg = _club_settings_dict(club_row)
    _saved = str(_cfg.get("syltek_url") or "").strip()
    if _saved:
        return _saved
    _env = str(settings.syltek_url or "").strip()
    if _env:
        return _env
    _slug = str((club_row or {}).get("slug") or "").strip().lower()
    _name = str((club_row or {}).get("name") or "").strip().lower()
    if "padelplus" in _slug or "padelplus" in _name:
        return _DEFAULT_SYLTEK_LOGIN_URL
    return _DEFAULT_SYLTEK_LOGIN_URL


def _syltek_defaults_for_club(club_row: dict | None) -> tuple[str, str, str]:
    _cfg = _club_settings_dict(club_row)
    _url = _default_syltek_url(club_row)
    _user = str(_cfg.get("syltek_user") or settings.syltek_user or "").strip()
    _pass = str(_cfg.get("syltek_password") or settings.syltek_password or "").strip()
    return _url, _user, _pass


def _save_syltek_settings_for_club(
    db_obj,
    club_id: str | None,
    *,
    url: str | None = None,
    user: str | None = None,
    password: str | None = None,
    courts: dict | None = None,
) -> None:
    """
    Persiste configuración Syltek dentro de clubs.settings para el club activo.
    Se hace merge con el resto de settings para no perder información del club.
    """
    if db_obj is None or not club_id:
        return
    _row = db_obj.get_club_by_id(club_id)
    if not _row:
        return
    _settings = dict(_club_settings_dict(_row))
    if url is not None:
        _settings["syltek_url"] = str(url).strip()
    if user is not None:
        _settings["syltek_user"] = str(user).strip()
    if password is not None:
        _settings["syltek_password"] = str(password).strip()
    if courts is not None:
        _settings["syltek_courts"] = dict(courts)
    db_obj._c.table("clubs").update({"settings": _settings}).eq("id", club_id).execute()


def _division_option_maps() -> tuple[list[str], dict[str, str]]:
    keys: list[str] = []
    labels: dict[str, str] = {}
    for _cat in TournamentCategory:
        for _sub in TournamentSubcategory:
            _key = f"{_cat.value}:{_sub.value}"
            keys.append(_key)
            labels[_key] = f"{_cat.icon} {_cat.label} {_sub.label}"
    return keys, labels


def _legacy_division_key(t_obj) -> str | None:
    if t_obj is None:
        return None
    _cat = getattr(t_obj, "category", None)
    _sub = getattr(t_obj, "subcategory", None)
    if _cat is None or _sub is None:
        return None
    return f"{_cat.value}:{_sub.value}"


def _parse_division_key(key: str) -> tuple[TournamentCategory | None, TournamentSubcategory | None]:
    try:
        _cat_raw, _sub_raw = key.split(":", 1)
        return TournamentCategory(_cat_raw), TournamentSubcategory(_sub_raw)
    except Exception:
        return None, None


def _division_badges_html(t_obj) -> str:
    _keys, _labels = _division_option_maps()
    _valid_keys = set(_keys)
    _divs = [d for d in (getattr(t_obj, "divisions", []) or []) if d in _valid_keys]
    if not _divs:
        _legacy = _legacy_division_key(t_obj)
        if _legacy:
            _divs = [_legacy]
    _html_parts = []
    for _d in _divs:
        _cat, _sub = _parse_division_key(_d)
        if _cat is None or _sub is None:
            continue
        _cls = {"masculino": "t-cat-masc", "femenino": "t-cat-fem", "mixto": "t-cat-mix"}[_cat.value]
        _html_parts.append(f'<span class="{_cls}">{_cat.icon} {_cat.label}</span>')
        _html_parts.append(f'<span class="t-subcat">{_sub.label}</span>')
    return "".join(_html_parts)


# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PadelPlus Club",
    page_icon="P",
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
        "db_tournament_id": None,
        # Navegación
        "_nav_page": "home",
        # Flag de carga desde DB — se resetea en logout para que recargue al volver a entrar
        "_db_phase_loaded": False,
        "_db_tournament_loaded": False,
        # Club activo cargado en memoria (superadmin).
        "_active_club_id": None,
        "_t_config_divisions_source_id": None,
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
    if not is_authenticated() and _db is not None:
        restore_session_from_cookie(_db)
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
                    if _loaded_phase is not None:
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
        if _cid_load and _db is not None and st.session_state.get("tournament") is None and not st.session_state.get("_db_tournament_loaded"):
            st.session_state["_db_tournament_loaded"] = True
            try:
                _t_row = _db.get_latest_tournament(_cid_load)
                if _t_row:
                    _loaded_t = tournament_from_db(_t_row)
                    st.session_state["tournament"] = _loaded_t
                    st.session_state["db_tournament_id"] = _t_row["id"]
                    st.session_state.pop("t_courts_list", None)
                    st.session_state.pop("t_config_divisions", None)
                    st.session_state["_t_config_divisions_source_id"] = None
            except Exception:
                pass  # BD no disponible o torneo inválido — ignorar silenciosamente

# ---------------------------------------------------------------------------
# Sidebar — navegación
# ---------------------------------------------------------------------------

_s = st.session_state
page = _s.get("_nav_page", "home")

st.sidebar.markdown(
    '<div class="pp-brand">'
    '<div class="pp-brand-row">'
    '<div class="pp-brand-mark">P+</div>'
    '<div>'
    '<div class="pp-brand-title">PadelPlus</div>'
    '<div class="pp-brand-subtitle">Club manager</div>'
    '</div></div></div>',
    unsafe_allow_html=True,
)

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
            _selected_club_id = _club_options[_sel_name]
            st.session_state["superadmin_selected_club_id"] = _selected_club_id
            st.session_state["superadmin_selected_club_name"] = _sel_name
            _club_name_sidebar = _sel_name

            # Cambio de club: limpiar estado cargado del club anterior para evitar datos mezclados.
            _active_club_id = st.session_state.get("_active_club_id")
            if _active_club_id != _selected_club_id:
                st.session_state["_active_club_id"] = _selected_club_id
                _reset_club_runtime_state()
                st.rerun()
        else:
            st.sidebar.markdown(
                '<div class="pp-empty-club">⚠ Sin clubs — crea uno en Administración</div>',
                unsafe_allow_html=True,
            )
    else:
        _club_name_sidebar = current_club_name()
        # Mantener el club activo sincronizado para club_admin.
        st.session_state["_active_club_id"] = current_club_id()

    _role_txt = "Super Admin" if is_superadmin() else "Admin"
    _club_txt = _club_name_sidebar or "Sin club"
    st.sidebar.markdown(
        f'<div class="pp-user-card">'
        f'<div class="pp-user-name">{escape(str(_user["display_name"]))}</div>'
        f'<div class="pp-user-meta">{escape(_role_txt)} · {escape(_club_txt)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.sidebar.button("↪  Cerrar sesión", use_container_width=True, key="btn_logout"):
        logout()
else:
    _club_name_sidebar = _s.get("club_name", "")

if _db_ok and is_authenticated() and is_superadmin() and not _club_name_sidebar and page not in {"home", "admin"}:
    _s["_nav_page"] = "home"
    st.rerun()

st.sidebar.markdown('<div class="pp-nav-section">Principal</div>', unsafe_allow_html=True)
_sidebar_button("⌂  Inicio",                   "home",        page, "nav_home")
_sidebar_button("◈  Configuración del club",   "club_config", page, "nav_club_config")

_has_results = bool(getattr(_s.phase, "match_results", []) if _s.phase else [])
_R_STEPS = [
    ("config",    "Configurar fase",    "Define fechas, pistas y parámetros",  _s.phase is not None),
    ("import",    "Importar datos",     "Sube grupos, parejas y reservas",      _s.data_loaded),
    ("generate",  "Generar calendario", "Crea los partidos automáticamente",    _s.matches_generated),
    ("results",   "Registrar resultados", "Introduce los marcadores de cada partido", _has_results),
    ("standings", "Clasificación",      "Ranking automático por puntos",         _has_results),
    ("export",    "Exportar",           "Excel, mensajes WhatsApp y más",       _s.matches_scheduled),
    ("review",    "Revisión",           "Comprueba conflictos y ajustes",       _s.matches_scheduled and _s.get("schedule_violations") is not None),
    ("syltek",    "Publicar en Syltek", "Reserva pistas automáticamente",       False),
]
_IS_RANKING = page in {k for k, *_ in _R_STEPS}

_T_OBJ   = _s.get("tournament")
_T_SCHED = getattr(_T_OBJ, "scheduled_count", 0) if _T_OBJ is not None else 0
_t_has_results = any(getattr(m, "is_played", False) for m in getattr(_T_OBJ, "matches", [])) if _T_OBJ else False
_T_STEPS = [
    ("t_config",   "Configurar torneo",  "Nombre, categoría, formato y pistas",  _T_OBJ is not None),
    ("t_pairs",    "Añadir parejas",     "Registra las parejas participantes",    _T_OBJ is not None and len(getattr(_T_OBJ, "pairs",    [])) > 0),
    ("t_generate", "Generar estructura", "Crea grupos y/o cuadro",                _T_OBJ is not None and len(getattr(_T_OBJ, "matches",  [])) > 0),
    ("t_schedule", "Asignar horarios",   "Planificación automática",              _T_SCHED > 0),
    ("t_results",  "Registrar resultados", "Marcadores y avance del cuadro",      _t_has_results),
    ("t_export",   "Exportar",           "Descarga el Excel del torneo",          _T_SCHED > 0),
]
_IS_TOURNAMENT = page in {k for k, *_ in _T_STEPS}

st.sidebar.markdown('<div class="pp-nav-section">Flujos guiados</div>', unsafe_allow_html=True)
_sidebar_workflow("◫  Ranking",  _R_STEPS, page, "nav_r", expanded=_IS_RANKING)
_sidebar_workflow("◈  Torneos",  _T_STEPS, page, "nav_t", expanded=_IS_TOURNAMENT)

if _db_ok and is_superadmin():
    st.sidebar.markdown('<div class="pp-nav-section">Sistema</div>', unsafe_allow_html=True)
    _sidebar_button("⚙  Administración", "admin", page, "nav_admin")

_dry = _s.get("dry_run", True)
_mode_txt = "Modo seguro" if _dry else "⚡ Escritura real"
st.sidebar.markdown(
    f'<div class="pp-sidebar-footer"><span class="pp-mode-pill">{"🔒  " if _dry else "⚡  "}{escape(_mode_txt)}</span></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# TORNEOS — helpers (deben definirse antes del routing)
# ---------------------------------------------------------------------------

def _t_header(step_num: int, step_title: str, step_hint: str) -> None:
    import datetime as _dt_mod
    t = st.session_state.get("tournament")
    if t and getattr(t, "is_top", False):
        _cat_html = _division_badges_html(t)
        _dates = t.start_date.strftime("%d/%m/%Y") + (f" – {t.end_date.strftime('%d/%m/%Y')}" if t.end_date != t.start_date else "")
        st.markdown(
            f'<div class="t-top-banner"><div class="t-top-name">🏆 {t.name}</div>'
            f'<div class="t-top-meta">📅 {_dates}' + (f' &nbsp;|&nbsp; 📍 {t.location}' if t.location else '') + f'</div>'
            f'<div style="margin-top:.5rem">{_cat_html}</div>' + (f'<div class="t-top-prize">🥇 {t.prize}</div>' if t.prize else '') + f'</div>',
            unsafe_allow_html=True,
        )
    else:
        _page_header("🏆", f"Torneos — {step_title}", step_hint)
    _steps_bc = ["⚙️ Config","👥 Parejas","🎯 Estructura","🗓️ Horarios","🏆 Resultados","📤 Exportar"]
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
    _keys = ["t_config","t_pairs","t_generate","t_schedule","t_results","t_export"]
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
# PÁGINA: Inicio
# ---------------------------------------------------------------------------

if page == "home":
    _home_club = _club_name_sidebar or current_club_name() if (_db_ok and is_authenticated()) else _s.get("club_name", "Club demo")
    _groups_home = list(_s.get("groups") or [])
    _pairs_home = sum(len(getattr(g, "pairs", []) or []) for g in _groups_home)
    _phase_home = _s.get("phase")
    _courts_home = len(getattr(_phase_home, "courts", []) or []) if _phase_home is not None else 0
    _result_home = _s.get("schedule_result")
    _scheduled_home = len(getattr(_result_home, "scheduled", []) or []) if _result_home is not None else 0
    _pending_home = len(_s.get("matches") or []) if _s.get("matches_generated") and not _scheduled_home else max(len(_s.get("matches") or []) - _scheduled_home, 0)

    if _db_ok and is_authenticated() and is_superadmin() and not _club_name_sidebar:
        # ── Onboarding para superadmin sin clubs ──────────────────────────
        _dashboard_hero(
            "Bienvenido a PadelPlus",
            "Tu plataforma de gestión de pádel. Empieza creando el primer club para activar todas las funciones.",
            "✦  Configuración inicial",
        )
        _info_grid([
            ("1. Crea un club", "Registra el nombre del club y su identificador interno. Cada club tiene sus propios datos y usuarios."),
            ("2. Añade un administrador", "Crea un usuario club_admin vinculado al club para que pueda acceder solo a su información."),
            ("3. Configura ranking y torneos", "Con el club activo podrás configurar fases de ranking, pistas, parejas e importar datos."),
            ("4. Lista para mostrar", "Con datos de ejemplo la aplicación se ve como un producto terminado, lista para enseñar."),
        ])
        st.markdown("")
        _c1, _c2, _c3 = st.columns([2, 1, 1])
        with _c1:
            if st.button("🚀  Ir a Administración", type="primary", use_container_width=True):
                _nav_to("admin")
    else:
        # ── Dashboard del club ────────────────────────────────────────────
        _dashboard_hero(
            f"{_home_club or 'Tu club'} — Panel de control",
            "Gestiona rankings, torneos, pistas y calendarios desde un único lugar.",
            "✦  PadelPlus",
        )
        _kpi_grid([
            ("Grupos",   len(_groups_home),                                      "en el ranking activo"),
            ("Parejas",  _pairs_home,                                             "jugadores inscritos"),
            ("Partidos", _scheduled_home or len(_s.get("matches") or []),         "en el calendario"),
            ("Pistas",   _courts_home,                                            "configuradas"),
        ])

        st.markdown(
            '<div style="font-size:.7rem;font-weight:800;letter-spacing:.12em;'
            'text-transform:uppercase;color:#7088a0;margin:0 0 .8rem">Módulos disponibles</div>',
            unsafe_allow_html=True,
        )
        _info_grid([
            ("📊  Ranking",        "Configura fases, importa grupos y parejas, genera el calendario y exporta comunicaciones a jugadores."),
            ("🏆  Torneos",        "Crea torneos con grupos, cuadro eliminatorio o formato mixto. Asigna horarios y exporta en Excel."),
            ("🗓️  Calendario",     "Revisa la distribución de partidos, detecta conflictos y ajusta reservas antes de publicar."),
            ("🛠️  Administración", "Gestiona clubs, usuarios y permisos. Cada club accede solo a sus propios datos."),
        ])

        st.markdown("")
        _qa1, _qa2, _qa3 = st.columns(3)
        with _qa1:
            if st.button("📊  Gestionar ranking", type="primary", use_container_width=True):
                _nav_to("config")
        with _qa2:
            if st.button("🏆  Crear torneo", use_container_width=True):
                _nav_to("t_config")
        with _qa3:
            if st.button("⚙️  Config. del club", use_container_width=True):
                _nav_to("club_config")


# ---------------------------------------------------------------------------
# PÁGINA 0: Configuración del club
# ---------------------------------------------------------------------------

elif page == "club_config":
    _page_header("🏢", "Configuración del club", "Datos del club que se guardan automáticamente")

    _cid = current_club_id() if _db_ok else None
    _club_row = _db.get_club_by_id(_cid) if (_db_ok and _db and _cid) else None

    # Leer settings guardados
    _settings = _club_settings_dict(_club_row)
    _syl_default_url, _syl_default_user, _syl_default_pass = _syltek_defaults_for_club(_club_row)

    col1, col2 = st.columns(2)
    with col1:
        _section_start("🏢", "Datos del club")
        _cc_name    = st.text_input("Nombre del club", value=_club_row["name"] if _club_row else _s.get("club_name",""))
        _cc_address = st.text_input("Dirección", value=_settings.get("address",""), placeholder="Calle Mayor 1, Madrid")
        _cc_phone   = st.text_input("Teléfono", value=_settings.get("phone",""),   placeholder="+34 600 000 000")
        _cc_email   = st.text_input("Email de contacto", value=_settings.get("email",""), placeholder="info@miclub.es")
        _cc_web     = st.text_input("Web", value=_settings.get("web",""),           placeholder="https://miclub.es")
        _section_start("🔗", "Integración Syltek")
        _cc_syl_url = st.text_input(
            "URL de login Syltek",
            value=_syl_default_url,
            placeholder="https://padelplus.syltek.com/system/account/login",
            help="Puedes pegar la URL completa de login; el conector la normaliza automáticamente.",
        )
        _cc_syl_user = st.text_input("Usuario Syltek", value=_syl_default_user)
        _cc_store_syl_pass = st.checkbox(
            "Guardar contraseña de Syltek en este club",
            value=bool(_syl_default_pass),
            help="Si desmarcas esta opción, la contraseña no se guardará en la configuración del club.",
        )
        _cc_syl_pass = st.text_input(
            "Contraseña Syltek",
            type="password",
            value=_syl_default_pass if _cc_store_syl_pass else "",
            placeholder="••••••••",
        )

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
        _new_settings = dict(_settings)
        _new_settings.update({
            "address": _cc_address, "phone": _cc_phone, "email": _cc_email,
            "web": _cc_web, "num_courts": _cc_courts, "indoor_courts": _cc_indoor,
            "open_time": str(_cc_open), "close_time": str(_cc_close), "notes": _cc_notes,
            "syltek_url": (_cc_syl_url or "").strip(),
            "syltek_user": (_cc_syl_user or "").strip(),
        })
        if _cc_store_syl_pass:
            _new_settings["syltek_password"] = (_cc_syl_pass or "").strip()
        else:
            _new_settings.pop("syltek_password", None)
        st.session_state["club_name"] = _cc_name
        for _k in ("syl_url", "syl_user", "syl_pass", "syl_imp_url", "syl_imp_user", "syl_imp_pass"):
            st.session_state.pop(_k, None)
        if _db_ok and _db and _cid:
            try:
                # Guardar settings en la tabla clubs
                _db._c.table("clubs").update({"name": _cc_name, "settings": _new_settings}).eq("id", _cid).execute()
                st.success("✅ Configuración del club (incluido Syltek) guardada en la base de datos.")
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
    _page_header("⚙️", "Configurar fase de ranking",
                 "Define los parámetros de esta fase: fechas, pistas y horarios de juego")

    # Leer datos del club para pre-rellenar valores
    _cfg_cid      = current_club_id() if _db_ok else None
    _cfg_club_row = _db.get_club_by_id(_cfg_cid) if (_db_ok and _db and _cfg_cid) else None
    _cfg_settings = (_cfg_club_row.get("settings") or {}) if _cfg_club_row else {}
    _cfg_club_name = (_cfg_club_row["name"] if _cfg_club_row else _s.get("club_name", "Mi Club"))
    _cfg_n_courts_default = int(_cfg_settings.get("num_courts", 4))
    _cfg_open_default  = _cfg_settings.get("open_time",  "09:00")
    _cfg_close_default = _cfg_settings.get("close_time", "22:00")

    # Pre-rellenar con valores de la fase existente si hay una guardada
    _ep = st.session_state.phase  # existing phase

    # ── Fila de estado (si ya hay fase guardada) ───────────────────────────
    if _ep is not None:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:.6rem;'
            f'background:rgba(0,200,83,.08);border:1px solid rgba(0,200,83,.25);'
            f'border-radius:10px;padding:.6rem 1rem;margin-bottom:1rem">'
            f'<span style="font-size:1.1rem">✅</span>'
            f'<span style="font-size:.9rem;color:#00843d;font-weight:600">'
            f'Fase activa: <strong>{_ep.name}</strong> · '
            f'{_ep.start_date} → {_ep.end_date} · '
            f'{len(_ep.courts)} pistas</span></div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        _section_start("📅", "Identificación y fechas")
        _cfg_phase_name = st.text_input(
            "Nombre de la fase",
            value=_ep.name if _ep else "Ranking Primavera 2026",
            placeholder="Ej: Ranking Primavera 2026",
        )
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            _cfg_start = st.date_input("Inicio", value=_ep.start_date if _ep else date.today() + timedelta(days=7))
        with _cc2:
            _cfg_end   = st.date_input("Fin",    value=_ep.end_date   if _ep else date.today() + timedelta(days=49))

        st.markdown("")
        _section_start("⏰", "Horario de juego")
        _cfg_open_val  = _ep.day_start_time if _ep else (
            time(int(_cfg_open_default[:2]),  int(_cfg_open_default[3:5]))
            if isinstance(_cfg_open_default, str) else time(9, 0)
        )
        _cfg_close_val = _ep.day_end_time if _ep else (
            time(int(_cfg_close_default[:2]), int(_cfg_close_default[3:5]))
            if isinstance(_cfg_close_default, str) else time(22, 0)
        )
        _h1, _h2 = st.columns(2)
        with _h1:
            _cfg_start_h = st.time_input("Primera hora de juego", value=_cfg_open_val)
        with _h2:
            _cfg_end_h   = st.time_input("Última hora de juego",  value=_cfg_close_val)
        st.caption("💡 Los partidos se programarán dentro de esta franja horaria.")

    with col2:
        _section_start("🏟️", "Pistas para esta fase")
        _cfg_n_courts = st.number_input(
            "Número de pistas disponibles",
            min_value=1, max_value=30,
            value=len(_ep.courts) if _ep and _ep.courts else _cfg_n_courts_default,
            help=f"Tu club tiene {_cfg_n_courts_default} pistas registradas.",
        )
        # Nombres personalizados de pistas
        _court_names_default = (
            [c.name for c in _ep.courts] if _ep and _ep.courts else
            [f"Pista {i}" for i in range(1, int(_cfg_n_courts) + 1)]
        )
        with st.expander("Personalizar nombres de pistas", expanded=False):
            _court_names = []
            for _ci in range(int(_cfg_n_courts)):
                _default_name = _court_names_default[_ci] if _ci < len(_court_names_default) else f"Pista {_ci+1}"
                _court_names.append(st.text_input(f"Pista {_ci+1}", value=_default_name, key=f"cname_{_ci}"))

        st.markdown("")
        _section_start("🎾", "Parámetros de partido")
        _cfg_duration = st.select_slider(
            "Duración de cada partido",
            options=[60, 75, 90, 105, 120],
            value=_ep.match_duration_minutes if _ep else 90,
            format_func=lambda x: f"{x} min",
        )
        _cfg_max_week = st.slider(
            "Máx. partidos por pareja / semana", 1, 5,
            value=getattr(_ep, "max_matches_per_week", 1) if _ep else 1,
        )
        _cfg_min_days = st.slider(
            "Mín. días entre partidos de la misma pareja", 0, 7,
            value=getattr(_ep, "min_days_between_matches", 2) if _ep else 2,
            help="0 = sin restricción",
        )

        st.markdown("")
        _section_start("🏆", "Reglas de puntuación")
        _ep_rules = getattr(_ep, "scoring_rules", None) if _ep else None
        _pc1, _pc2, _pc3 = st.columns(3)
        with _pc1:
            _cfg_pts_win  = st.number_input("Puntos por victoria", min_value=1, max_value=10,
                                            value=getattr(_ep_rules, "points_win", 3) if _ep_rules else 3)
        with _pc2:
            _cfg_pts_draw = st.number_input("Puntos por empate", min_value=0, max_value=5,
                                            value=getattr(_ep_rules, "points_draw", 1) if _ep_rules else 1)
        with _pc3:
            _cfg_pts_loss = st.number_input("Puntos por derrota", min_value=0, max_value=5,
                                            value=getattr(_ep_rules, "points_loss", 0) if _ep_rules else 0)
        _cfg_bonus = st.checkbox(
            "Punto extra por ganar sin ceder ningún set",
            value=bool(getattr(_ep_rules, "bonus_clean_sheet", 0)) if _ep_rules else False,
        )

        with st.expander("⚙️ Opciones avanzadas", expanded=False):
            _cfg_seed_on = st.checkbox("Resultado reproducible (semilla fija)", value=True)
            _cfg_seed    = st.number_input("Semilla", value=42, step=1) if _cfg_seed_on else None

    st.divider()

    _save_col, _next_col = st.columns([3, 1])
    with _save_col:
        _save_btn = st.button("💾 Guardar configuración de fase", type="primary", use_container_width=True)
    with _next_col:
        if st.button("Importar datos →", use_container_width=True, disabled=_ep is None):
            st.session_state["_nav_page"] = "import"; st.rerun()

    if _save_btn:
        _errs_phase = validate_phase_dates(_cfg_start, _cfg_end)
        if _errs_phase:
            for _e in _errs_phase:
                st.error(_e)
        else:
            from uuid import uuid4 as _uuid4
            from src.models import BalanceWeights
            _new_courts = [
                Court.model_construct(
                    id=f"court_{i}",
                    name=_court_names[i-1] if i <= len(_court_names) else f"Pista {i}",
                    indoor=False, active=True,
                )
                for i in range(1, int(_cfg_n_courts) + 1)
            ]
            from src.ranking_scorer import ScoringRules as _ScoringRules
            _new_rules = _ScoringRules(
                points_win=int(_cfg_pts_win),
                points_draw=int(_cfg_pts_draw),
                points_loss=int(_cfg_pts_loss),
                bonus_clean_sheet=1 if _cfg_bonus else 0,
            )
            # Preservar resultados ya registrados al re-guardar una fase existente
            _preserved_results = list(getattr(_ep, "match_results", [])) if _ep else []
            _new_phase = RankingPhase.model_construct(
                id=str(_uuid4()),
                name=_cfg_phase_name,
                start_date=_cfg_start,
                end_date=_cfg_end,
                courts=_new_courts,
                groups=st.session_state.groups,
                bookings=st.session_state.bookings,
                match_duration_minutes=_cfg_duration,
                day_start_time=_cfg_start_h,
                day_end_time=_cfg_end_h,
                max_matches_per_week=_cfg_max_week,
                min_days_between_matches=_cfg_min_days,
                random_seed=int(_cfg_seed) if _cfg_seed is not None else None,
                balance_weights=BalanceWeights.model_construct(
                    same_hour_penalty=10.0, same_weekday_penalty=6.0,
                    same_court_penalty=2.0, day_load_penalty=1.5,
                    court_load_penalty=1.0, early_day_bonus=0.5,
                    preferred_slot_bonus=25.0, global_hour_penalty=5.0,
                    global_weekday_penalty=4.0, late_hour_penalty=2.5,
                    top_candidates_pool=4,
                ),
                scoring_rules=_new_rules,
                match_results=_preserved_results,
            )
            st.session_state.phase  = _new_phase
            st.session_state.courts = _new_courts
            st.session_state["club_name"] = _cfg_club_name

            if _db_ok and _db is not None and _cfg_cid:
                try:
                    _payload = phase_to_db(_new_phase, _cfg_cid, st.session_state.get("db_phase_id"))
                    _saved   = _db.upsert_phase(
                        club_id=_cfg_cid, name=_payload["name"],
                        start_date=_payload["start_date"], end_date=_payload["end_date"],
                        phase_config=_payload["phase_config"], groups_data=_payload["groups_data"],
                        bookings_data=_payload["bookings_data"], schedule_result=None,
                        phase_id=_payload["phase_id"],
                    )
                    st.session_state["db_phase_id"] = _saved["id"]
                    st.success(f"✅ Fase **{_cfg_phase_name}** guardada correctamente.")
                except Exception as _e:
                    st.warning(f"⚠️ No se pudo guardar en BD: {_e}")
            else:
                st.success(f"✅ Fase **{_cfg_phase_name}** guardada en sesión.")
            st.rerun()

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
                # Al reimportar grupos los partidos anteriores quedan obsoletos — limpiar
                st.session_state.schedule_result  = None
                st.session_state.matches          = []
                st.session_state.matches_generated = False
                st.session_state.matches_scheduled = False
                # Actualizar fase si existe
                if st.session_state.phase:
                    st.session_state.phase.groups = groups
                    # Persistir en Supabase (sin schedule_result para evitar datos huérfanos)
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
                                    schedule_result=None,  # reseteado intencionadamente
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
        _imp_cid = current_club_id() if _db_ok else None
        _imp_club_row = _db.get_club_by_id(_imp_cid) if (_db_ok and _db and _imp_cid) else None
        _imp_url_default, _imp_user_default, _imp_pass_default = _syltek_defaults_for_club(_imp_club_row)

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            syl_imp_url = st.text_input(
                "URL Syltek",
                value=_imp_url_default,
                key="syl_imp_url",
            )
            syl_imp_user = st.text_input(
                "Usuario",
                value=_imp_user_default,
                key="syl_imp_user",
            )
        with col_c2:
            syl_imp_pass = st.text_input("Contraseña", type="password", value=_imp_pass_default, key="syl_imp_pass")

        if st.button("💾 Guardar credenciales Syltek en este club", key="btn_save_syl_imp_creds"):
            if not syl_imp_url or not syl_imp_user or not syl_imp_pass:
                st.warning("Completa URL, usuario y contraseña para guardarlas.")
            elif _db_ok and _db and _imp_cid:
                try:
                    _save_syltek_settings_for_club(
                        _db,
                        _imp_cid,
                        url=syl_imp_url,
                        user=syl_imp_user,
                        password=syl_imp_pass,
                    )
                    st.success("✅ Credenciales Syltek guardadas para este club.")
                except Exception as _e_syl_save:
                    st.warning(f"⚠️ No se pudieron guardar: {_e_syl_save}")
            else:
                st.info("ℹ️ Sin base de datos activa; no se pueden persistir credenciales.")

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
                        if _db_ok and _db and _imp_cid:
                            try:
                                _save_syltek_settings_for_club(
                                    _db,
                                    _imp_cid,
                                    url=syl_imp_url,
                                    user=syl_imp_user,
                                    password=syl_imp_pass,
                                )
                            except Exception:
                                pass
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
                                try:
                                    parts = new_val.split(":")
                                    match_obj.suggested_start_time = time(int(parts[0]), int(parts[1]))
                                except (IndexError, ValueError):
                                    pass  # formato inesperado — ignorar sin crashear
                            else:
                                match_obj.suggested_start_time = new_val
                            schedule_fields_changed = True
                        elif col == "Fin" and new_val is not None:
                            if isinstance(new_val, str):
                                try:
                                    parts = new_val.split(":")
                                    match_obj.suggested_end_time = time(int(parts[0]), int(parts[1]))
                                except (IndexError, ValueError):
                                    pass
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
# PÁGINA: Registrar resultados
# ---------------------------------------------------------------------------

elif page == "results":
    from src.ranking_scorer import MatchResult, SetScore
    _page_header("📝", "Registrar resultados", "Introduce el marcador de cada partido (formato set: 6-4)")

    _rphase = st.session_state.phase
    _rmatches = st.session_state.get("matches") or []

    if _rphase is None or not _rmatches:
        _empty_state("⚡", "No hay partidos",
                     "Primero <strong>genera el calendario</strong> en el paso anterior.")
        st.stop()

    # Reglas de puntuación actuales
    _rules = getattr(_rphase, "scoring_rules", None)
    if _rules is None:
        from src.ranking_scorer import ScoringRules
        _rules = ScoringRules()
        _rphase.scoring_rules = _rules

    # Mapa de resultados ya guardados {match_id: MatchResult}
    _existing = {r.match_id: r for r in getattr(_rphase, "match_results", [])}

    def _set_to_str(gs) -> str:
        return f"{gs.games_1}-{gs.games_2}" if (gs.games_1 or gs.games_2) else ""

    def _parse_set(text):
        """'6-4' -> SetScore(6,4). Vacío, None o NaN -> None."""
        if text is None or (isinstance(text, float) and pd.isna(text)):
            return None
        text = str(text).strip()
        if not text:
            return None
        for sep in ("-", "/", ":"):
            if sep in text:
                a, _, b = text.partition(sep)
                try:
                    return SetScore(games_1=int(a.strip()), games_2=int(b.strip()))
                except ValueError:
                    return None
        return None

    # Construir filas para el editor agrupadas por grupo
    _groups_order = {}
    for m in _rmatches:
        _groups_order.setdefault(m.group_name or "Sin grupo", []).append(m)

    st.caption("Introduce los sets como **6-4**. Deja en blanco los no jugados. WO = walkover (victoria sin jugar).")

    _edited_results = {}
    for _gname, _gmatches in _groups_order.items():
        _section_start("🎾", _gname)
        _rows = []
        for m in _gmatches:
            _ex = _existing.get(m.id)
            _s1 = _set_to_str(_ex.sets[0]) if _ex and len(_ex.sets) > 0 else ""
            _s2 = _set_to_str(_ex.sets[1]) if _ex and len(_ex.sets) > 1 else ""
            _s3 = _set_to_str(_ex.sets[2]) if _ex and len(_ex.sets) > 2 else ""
            _wo = ""
            if _ex and _ex.walkover_winner_id == m.pair_1.id:
                _wo = m.pair_1.display_name
            elif _ex and _ex.walkover_winner_id == m.pair_2.id:
                _wo = m.pair_2.display_name
            _rows.append({
                "_match_id": m.id,
                "Partido": f"{m.pair_1.display_name}  vs  {m.pair_2.display_name}",
                "Set 1": _s1, "Set 2": _s2, "Set 3": _s3,
                "WO": _wo,
            })
        _df = pd.DataFrame(_rows)
        _wo_opts = [""]
        for m in _gmatches:
            _wo_opts.extend([m.pair_1.display_name, m.pair_2.display_name])
        _edited = st.data_editor(
            _df,
            key=f"results_editor_{_gname}",
            hide_index=True,
            use_container_width=True,
            column_config={
                "_match_id": None,  # oculta
                "Partido":   st.column_config.TextColumn(disabled=True, width="large"),
                "Set 1":     st.column_config.TextColumn(width="small", help="ej. 6-4"),
                "Set 2":     st.column_config.TextColumn(width="small"),
                "Set 3":     st.column_config.TextColumn(width="small", help="solo si hubo tercer set"),
                "WO":        st.column_config.SelectboxColumn(options=sorted(set(_wo_opts)), width="medium"),
            },
        )
        # Mapear ediciones de vuelta a los match objects
        _match_by_id = {m.id: m for m in _gmatches}
        for _, _row in _edited.iterrows():
            _edited_results[_row["_match_id"]] = (_row, _match_by_id[_row["_match_id"]])

    st.divider()
    if st.button("💾 Guardar resultados", type="primary", use_container_width=True):
        _new_results = []
        for _mid, (_row, _m) in _edited_results.items():
            _wo_raw = _row.get("WO")
            _wo_name = "" if (_wo_raw is None or (isinstance(_wo_raw, float) and pd.isna(_wo_raw))) else str(_wo_raw).strip()
            _wo_id = None
            if _wo_name == _m.pair_1.display_name:
                _wo_id = _m.pair_1.id
            elif _wo_name == _m.pair_2.display_name:
                _wo_id = _m.pair_2.id

            _sets = []
            for _col in ("Set 1", "Set 2", "Set 3"):
                _ss = _parse_set(_row.get(_col))
                if _ss is not None:
                    _sets.append(_ss)

            if _sets or _wo_id:
                _new_results.append(MatchResult(
                    match_id=_mid, pair_1_id=_m.pair_1.id, pair_2_id=_m.pair_2.id,
                    group_id=_m.group_id, sets=_sets, walkover_winner_id=_wo_id,
                ))

        _rphase.match_results = _new_results
        st.session_state.phase = _rphase

        # Persistir en Supabase
        if _db_ok and _db is not None:
            _cid = current_club_id()
            _pid = st.session_state.get("db_phase_id")
            if _cid and _pid:
                try:
                    _payload = phase_to_db(_rphase, _cid, _pid)
                    _db.upsert_phase(
                        club_id=_cid, name=_payload["name"],
                        start_date=_payload["start_date"], end_date=_payload["end_date"],
                        phase_config=_payload["phase_config"], groups_data=_payload["groups_data"],
                        bookings_data=_payload["bookings_data"],
                        schedule_result=schedule_result_to_db(st.session_state.get("schedule_result")),
                        phase_id=_pid,
                    )
                except Exception as _e:
                    st.warning(f"⚠️ Guardado local OK, pero falló la BD: {_e}")

        st.success(f"✅ {len(_new_results)} resultados guardados.")
        st.session_state["_nav_page"] = "standings"
        st.rerun()


# ---------------------------------------------------------------------------
# PÁGINA: Clasificación
# ---------------------------------------------------------------------------

elif page == "standings":
    from src.ranking_scorer import compute_standings, standings_by_group, ScoringRules
    _page_header("🏅", "Clasificación", "Ranking automático calculado a partir de los resultados")

    _sphase = st.session_state.phase
    if _sphase is None:
        _empty_state("⚙️", "Sin fase configurada", "Configura una fase primero.")
        st.stop()

    _results = getattr(_sphase, "match_results", [])
    if not _results:
        _empty_state("📝", "Sin resultados todavía",
                     "Registra los marcadores en <strong>Registrar resultados</strong>.")
        st.stop()

    _rules = getattr(_sphase, "scoring_rules", None) or ScoringRules()

    # Mapas pareja → nombre y pareja → grupo
    _pair_names, _pair_group = {}, {}
    for g in _sphase.groups:
        for p in g.pairs:
            _pair_names[p.id] = p.display_name
            _pair_group[p.id] = g.id
    _group_label = {g.id: g.name for g in _sphase.groups}

    # Resumen de reglas activas
    _stat_chips(
        (f"{_rules.points_win} pts victoria", "green", "🏆"),
        (f"{_rules.points_draw} empate", "orange", "🤝"),
        (f"{_rules.points_loss} derrota", "red", "❌"),
        (f"{len(_results)} partidos jugados", "green", "🎾"),
    )

    _by_group = standings_by_group(_results, _pair_names, _rules, _pair_group)

    for _gid, _table in _by_group.items():
        _section_start("🏅", _group_label.get(_gid, "Clasificación"))
        _rows = []
        for _pos, _s in enumerate(_table, 1):
            _medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(_pos, str(_pos))
            _rows.append({
                "#": _medal,
                "Pareja": _s.pair_name,
                "PJ": _s.played, "G": _s.won, "E": _s.drawn, "P": _s.lost,
                "Sets": f"{_s.sets_for}-{_s.sets_against}",
                "Juegos": f"{_s.games_for}-{_s.games_against}",
                "Dif": f"{_s.game_diff:+d}",
                "Pts": _s.points,
            })
        st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True,
                     column_config={"Pts": st.column_config.NumberColumn(width="small")})

    st.caption("PJ=Jugados · G=Ganados · E=Empatados · P=Perdidos · Pts=Puntos. "
               "Desempate: puntos → diferencia de sets → diferencia de juegos → victorias → cara a cara.")


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

    if phase is None or result is None:
        _empty_state("⚠️", "Datos de fase no disponibles",
                     "Recarga la página o vuelve a configurar la fase.")
        st.stop()
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
    from collections import Counter  # necesario en todo el bloque review
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
        # Separar "incidencias" de "partidos afectados":
        # una misma incidencia puede afectar a 1..N partidos y, además,
        # un mismo partido puede acumular varias incidencias.
        _affected_match_ids: set[str] = set()
        _availability_issue_match_ids: set[str] = set()
        _availability_types = {"availability_weekday", "availability_time_early", "availability_time_late"}
        for _v in violations:
            _is_availability = _v.get("type") in _availability_types
            for _m in _v.get("matches", []) or []:
                _mid = getattr(_m, "id", None)
                if _mid:
                    _affected_match_ids.add(_mid)
                    if _is_availability:
                        _availability_issue_match_ids.add(_mid)

        rv1, rv2, rv3, rv4, rv5 = st.columns(5)
        rv1.metric("Partidos con incidencias", len(_affected_match_ids))
        rv2.metric("Incidencias totales", vs["total"])
        rv3.metric("🔴 Errores",  vs["errors"])
        rv4.metric("🟡 Avisos",   vs["warnings"])
        rv5.metric("🔵 Info PF",  vs["infos"])
        st.caption(
            "Una incidencia es una regla incumplida. "
            "Un mismo partido puede tener varias incidencias."
        )

        # Señal de inconsistencia: avisos de disponibilidad en partidos no editados manualmente.
        _manually_modified_ids = {
            m.id
            for m in (result.scheduled + result.conflicts)
            if getattr(m, "status", None) == MatchStatus.MANUALLY_MODIFIED
        }
        _availability_without_manual_changes = (
            len(_availability_issue_match_ids) > 0
            and len(_availability_issue_match_ids & _manually_modified_ids) == 0
        )
        if _availability_without_manual_changes:
            st.warning(
                "Se detectaron incidencias de disponibilidad en partidos no editados manualmente. "
                "Esto sugiere revisar el parser de disponibilidad (Observaciones) o la validación."
            )

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

    _syl_cid = current_club_id() if _db_ok else None
    _syl_club_row = _db.get_club_by_id(_syl_cid) if (_db_ok and _db and _syl_cid) else None
    _syl_settings = _club_settings_dict(_syl_club_row)
    _syl_url_default, _syl_user_default, _syl_pass_default = _syltek_defaults_for_club(_syl_club_row)

    # Estado de sesión Syltek
    if "syltek_logged_in" not in st.session_state:
        st.session_state["syltek_logged_in"] = False
    if "syltek_courts" not in st.session_state:
        _saved_courts = _syl_settings.get("syltek_courts")
        st.session_state["syltek_courts"] = dict(_saved_courts) if isinstance(_saved_courts, dict) else {}
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
            value=_syl_url_default,
            key="syl_url",
            help="Puedes usar URL base o URL completa de login, por ejemplo: https://padelplus.syltek.com/system/account/login",
        )
    with col_user:
        syl_user = st.text_input(
            "Usuario",
            value=_syl_user_default,
            key="syl_user",
        )
    syl_pass = st.text_input("Contraseña", type="password", value=_syl_pass_default, key="syl_pass")

    if st.button("💾 Guardar credenciales de conexión", key="btn_save_syltek_creds"):
        if not syl_url or not syl_user or not syl_pass:
            st.warning("Completa URL, usuario y contraseña para guardarlas.")
        elif _db_ok and _db and _syl_cid:
            try:
                _save_syltek_settings_for_club(
                    _db,
                    _syl_cid,
                    url=syl_url,
                    user=syl_user,
                    password=syl_pass,
                )
                st.success("✅ Credenciales guardadas para este club.")
            except Exception as _e_syl2:
                st.warning(f"⚠️ No se pudieron guardar: {_e_syl2}")
        else:
            st.info("ℹ️ Sin base de datos activa; no se pueden persistir credenciales.")

    dry_run_toggle = st.toggle(
        "Modo seguro (DRY-RUN) — simula las reservas sin crearlas de verdad",
        value=st.session_state.get("dry_run", True),
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
                if _db_ok and _db and _syl_cid:
                    try:
                        _save_syltek_settings_for_club(
                            _db,
                            _syl_cid,
                            url=syl_url,
                            user=syl_user,
                            password=syl_pass,
                        )
                    except Exception:
                        pass
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
                    if _db_ok and _db and _syl_cid:
                        try:
                            _save_syltek_settings_for_club(_db, _syl_cid, courts=courts)
                        except Exception:
                            pass
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
            if _db_ok and _db and _syl_cid:
                try:
                    _save_syltek_settings_for_club(_db, _syl_cid, courts=manual_courts)
                except Exception:
                    pass
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
            if _db_ok and _db and _syl_cid:
                try:
                    _save_syltek_settings_for_club(_db, _syl_cid, courts=courts_edit)
                except Exception:
                    pass
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
        value=getattr(t, "is_top", False) if t else False,
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
    _section_start("🎾", "Categorías y subcategorías")
    _div_keys, _div_labels = _division_option_maps()
    _div_key_set = set(_div_keys)
    _current_divisions = [d for d in (getattr(t, "divisions", []) if t else []) if d in _div_key_set]
    if not _current_divisions:
        _legacy = _legacy_division_key(t)
        if _legacy and _legacy in _div_key_set:
            _current_divisions = [_legacy]

    _div_source_id = f"{getattr(t, 'id', 'new')}::{st.session_state.get('db_tournament_id') or ''}"
    if st.session_state.get("_t_config_divisions_source_id") != _div_source_id:
        st.session_state["t_config_divisions"] = list(_current_divisions)
        st.session_state["_t_config_divisions_source_id"] = _div_source_id

    _preset_masc = [f"{TournamentCategory.MASCULINO.value}:{_sub.value}" for _sub in TournamentSubcategory]
    _preset_fem = [f"{TournamentCategory.FEMENINO.value}:{_sub.value}" for _sub in TournamentSubcategory]
    _preset_mix = [f"{TournamentCategory.MIXTO.value}:{_sub.value}" for _sub in TournamentSubcategory]
    _preset_all = list(dict.fromkeys(_preset_masc + _preset_fem + _preset_mix))

    _preset_cols = st.columns(5)
    with _preset_cols[0]:
        if st.button("Masculino 1ª-5ª", key="t_div_preset_masc", use_container_width=True):
            st.session_state["t_config_divisions"] = list(_preset_masc)
            st.rerun()
    with _preset_cols[1]:
        if st.button("Femenino 1ª-5ª", key="t_div_preset_fem", use_container_width=True):
            st.session_state["t_config_divisions"] = list(_preset_fem)
            st.rerun()
    with _preset_cols[2]:
        if st.button("Mixto 1ª-5ª", key="t_div_preset_mix", use_container_width=True):
            st.session_state["t_config_divisions"] = list(_preset_mix)
            st.rerun()
    with _preset_cols[3]:
        if st.button("Todas", key="t_div_preset_all", use_container_width=True):
            st.session_state["t_config_divisions"] = list(_preset_all)
            st.rerun()
    with _preset_cols[4]:
        if st.button("Limpiar", key="t_div_preset_none", use_container_width=True):
            st.session_state["t_config_divisions"] = []
            st.rerun()

    t_divisions = st.multiselect(
        "Selecciona una o varias categorías del torneo",
        options=_div_keys,
        key="t_config_divisions",
        format_func=lambda k: _div_labels.get(k, k),
        help="Puedes combinar categorías, por ejemplo: Masculino 1ª-5ª, Femenino 1ª-5ª y Mixto 1ª-5ª.",
    )

    if t_divisions:
        _chips = []
        for _d in t_divisions:
            _cat, _sub = _parse_division_key(_d)
            if _cat is None or _sub is None:
                continue
            _cls = {"masculino": "t-cat-masc", "femenino": "t-cat-fem", "mixto": "t-cat-mix"}[_cat.value]
            _chips.append(f'<span class="{_cls}">{_cat.icon} {_cat.label}</span><span class="t-subcat">{_sub.label}</span>')
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:.35rem;margin:.35rem 0 0">{"".join(_chips)}</div>', unsafe_allow_html=True)
    else:
        st.caption("Sin categorías específicas (torneo abierto).")

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
        _primary_cat, _primary_sub = (None, None)
        if t_divisions:
            _primary_cat, _primary_sub = _parse_division_key(t_divisions[0])
        new_t = TournamentConfig(
            id=t.id if t else str(__import__("uuid").uuid4()),
            name=t_name,
            category=_primary_cat,
            subcategory=_primary_sub,
            divisions=t_divisions,
            is_top=t_is_top, prize=t_prize, location=t_location,
            start_date=t_start, end_date=t_end, courts=_courts_obj, pairs=_pairs_keep,
            format=t_format, match_duration_minutes=t_match_dur, rest_between_matches_min=t_rest,
            day_start_time=t_day_start, day_end_time=t_day_end,
            group_size=t_group_size, bracket_size=t_bracket_size,
            third_place_match=t_third_place, groups_qualifiers=t_qualifiers,
            groups=[], matches=[],
        )
        st.session_state["tournament"] = new_t
        # Persistir en Supabase
        if _db_ok and _db is not None:
            _t_cid = current_club_id()
            if _t_cid:
                try:
                    _t_payload = tournament_to_db(new_t, _t_cid, st.session_state.get("db_tournament_id"))
                    _t_saved   = _db.upsert_tournament(
                        club_id=_t_cid,
                        name=_t_payload["name"],
                        start_date=_t_payload["start_date"],
                        end_date=_t_payload["end_date"],
                        tournament_data=_t_payload["tournament_data"],
                        tournament_id=_t_payload["tournament_id"],
                    )
                    st.session_state["db_tournament_id"] = _t_saved["id"]
                except Exception as _te:
                    st.warning(f"⚠️ No se pudo guardar en BD: {_te}")
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

    # Divisiones del torneo (claves "cat:sub")
    _t_div_keys = list(getattr(t, "divisions", []) or [])
    _t_multi = len(_t_div_keys) > 1
    _, _div_labels_all = _division_option_maps()

    def _div_label(_k):
        return _div_labels_all.get(_k, _k)

    if _t_multi:
        st.info(f"💡 Torneo: **{t.name}** · {len(t.pairs)} parejas · "
                f"**{len(_t_div_keys)} categorías** · asigna cada pareja a su categoría")
    else:
        st.info(f"💡 Torneo: **{t.name}** · {len(t.pairs)} parejas inscritas · Formato: **{t.format.value}**")

    _section_start("👥", "Añadir parejas")
    pair_tab_a, pair_tab_b = st.tabs(["📝 Añadir manualmente", "📂 Importar CSV"])

    with pair_tab_a:
        if _t_multi:
            _sel_div = st.selectbox(
                "Categoría de la pareja", options=_t_div_keys,
                format_func=_div_label, key="tnp_div",
            )
        else:
            _sel_div = _t_div_keys[0] if _t_div_keys else None
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
                    division=_sel_div,
                )
                t.pairs.append(new_pair)
                t.groups = []; t.matches = []; t.division_draws = []
                st.success(f"✅ '{new_pair.display_name}' añadida{(' a ' + _div_label(_sel_div)) if _sel_div else ''}.")
                st.rerun()
            else:
                st.error("Rellena nombre de pareja y los dos jugadores.")

    with pair_tab_b:
        if _t_multi:
            _csv_div = st.selectbox(
                "Asignar las parejas del CSV a la categoría", options=["(usar columna 'division')"] + _t_div_keys,
                format_func=lambda k: k if k.startswith("(") else _div_label(k), key="tnp_csv_div",
            )
            _sample_csv = ("pair_name,player1_name,player2_name,player1_phone,player2_phone,seed,division\n"
                           "García / López,Carlos García,Marta López,+34600000001,+34600000002,1,masculino:1a\n"
                           "Ruiz / Martín,Ana Ruiz,Luis Martín,,,,femenino:1a\n")
        else:
            _csv_div = None
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
                        # División: columna CSV o selección fija
                        _row_div = None
                        if _t_multi:
                            if _csv_div and not _csv_div.startswith("("):
                                _row_div = _csv_div
                            elif "division" in row and not pd.isna(row.get("division", float("nan"))):
                                _cand = str(row["division"]).strip()
                                _row_div = _cand if _cand in _t_div_keys else None
                        elif _t_div_keys:
                            _row_div = _t_div_keys[0]
                        new_pairs_csv.append(TournamentPair(
                            name=str(row["pair_name"]).strip(), seed=_seed_val,
                            player_1=TournamentPlayer(name=str(row["player1_name"]).strip(), phone=str(row.get("player1_phone","")).strip() or None),
                            player_2=TournamentPlayer(name=str(row["player2_name"]).strip(), phone=str(row.get("player2_phone","")).strip() or None),
                            division=_row_div,
                        ))
                    _unassigned = sum(1 for p in new_pairs_csv if _t_multi and not p.division)
                    if _unassigned:
                        st.warning(f"⚠️ {_unassigned} parejas sin categoría válida — corrige la columna 'division' o elige una categoría fija.")
                    if st.button(f"✅ Importar {len(new_pairs_csv)} parejas", type="primary"):
                        t.pairs.extend(new_pairs_csv)
                        t.groups = []; t.matches = []; t.division_draws = []
                        st.success(f"✅ {len(new_pairs_csv)} parejas importadas."); st.rerun()
            except Exception as _csv_err:
                st.error(f"Error: {_csv_err}")

    st.divider()
    if t.pairs:
        _section_start("📋", f"Parejas inscritas ({len(t.pairs)})")
        def _pair_row(_pi, _pp):
            _r = {"#": _pi+1, "Pareja": _pp.display_name,
                  "Jugador 1": _pp.player_1.full_name, "Jugador 2": _pp.player_2.full_name,
                  "Cabeza serie": f"#{_pp.seed}" if _pp.seed else "—"}
            if _t_multi:
                _r = {"#": _pi+1, "Categoría": _div_label(_pp.division) if _pp.division else "⚠️ sin asignar",
                      "Pareja": _pp.display_name, "Jugador 1": _pp.player_1.full_name,
                      "Jugador 2": _pp.player_2.full_name,
                      "Cabeza serie": f"#{_pp.seed}" if _pp.seed else "—"}
            return _r
        # Ordenar por categoría cuando es multi
        _pairs_sorted = sorted(enumerate(t.pairs), key=lambda x: (x[1].division or "zzz")) if _t_multi else list(enumerate(t.pairs))
        st.dataframe([_pair_row(_i, _p) for _i, _p in _pairs_sorted], use_container_width=True, hide_index=True)
        if _t_multi:
            # Recuento por categoría
            from collections import Counter as _Counter
            _cnt = _Counter(_div_label(p.division) if p.division else "⚠️ sin asignar" for p in t.pairs)
            _stat_chips(*[(f"{v} · {k}", "green" if "sin asignar" not in k else "red", "🎾") for k, v in _cnt.items()])
        if st.button("🗑️ Vaciar lista de parejas", type="secondary"):
            t.pairs = []; t.groups = []; t.matches = []; t.division_draws = []; st.rerun()
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
    _tg_div_keys = list(getattr(t, "divisions", []) or [])
    _tg_multi = len(_tg_div_keys) > 1
    _, _tg_div_labels = _division_option_maps()
    _section_start("🎯", "Previsión del torneo")

    if _tg_multi:
        from collections import Counter as _Counter2
        _pc = _Counter2(p.division for p in t.pairs)
        st.markdown(f"**{len(_tg_div_keys)} categorías** · formato **{t.format.value}** · "
                    "cada categoría genera su propio cuadro, todas comparten pistas y horario.")
        _rows_prev = [{"Categoría": _tg_div_labels.get(k, k), "Parejas": _pc.get(k, 0)} for k in _tg_div_keys]
        st.dataframe(_rows_prev, use_container_width=True, hide_index=True)
        _no_pairs_divs = [k for k in _tg_div_keys if _pc.get(k, 0) < 2]
        if _no_pairs_divs:
            st.warning("⚠️ Estas categorías tienen menos de 2 parejas y no generarán cuadro: "
                       + ", ".join(_tg_div_labels.get(k, k) for k in _no_pairs_divs))
    elif t.format == TournamentFormat.GROUPS:
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
            # Persistir torneo con horarios asignados en Supabase
            if _db_ok and _db is not None:
                _t_cid2 = current_club_id()
                if _t_cid2:
                    try:
                        _t_p2    = tournament_to_db(t_sched, _t_cid2, st.session_state.get("db_tournament_id"))
                        _t_s2    = _db.upsert_tournament(
                            club_id=_t_cid2, name=_t_p2["name"],
                            start_date=_t_p2["start_date"], end_date=_t_p2["end_date"],
                            tournament_data=_t_p2["tournament_data"],
                            tournament_id=_t_p2["tournament_id"],
                        )
                        st.session_state["db_tournament_id"] = _t_s2["id"]
                    except Exception:
                        pass
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
# TORNEO — PASO 5: Registrar resultados + avance del cuadro
# ---------------------------------------------------------------------------

elif page == "t_results":
    from src.tournament_results import (
        register_result as _treg, clear_result as _tclear,
        tournament_champion as _tchamp, results_summary as _tsumm,
    )
    from src.tournament_models import MatchRound as _MR
    _t_header(5, "Registrar resultados", "Marcadores y avance automático del cuadro")
    t = st.session_state.get("tournament")
    if not t or not t.matches:
        st.warning("⚠️ Genera la estructura del torneo antes de registrar resultados.")
        if st.button("← Generar estructura"):
            st.session_state["_nav_page"] = "t_generate"; st.rerun()
        st.stop()

    def _persist_tournament(_tobj):
        if _db_ok and _db is not None:
            _cid = current_club_id()
            if _cid:
                try:
                    _p = tournament_to_db(_tobj, _cid, st.session_state.get("db_tournament_id"))
                    _sv = _db.upsert_tournament(
                        club_id=_cid, name=_p["name"],
                        start_date=_p["start_date"], end_date=_p["end_date"],
                        tournament_data=_p["tournament_data"],
                        tournament_id=_p["tournament_id"],
                    )
                    st.session_state["db_tournament_id"] = _sv["id"]
                except Exception as _e:
                    st.warning(f"⚠️ Guardado local OK, BD falló: {_e}")

    # Resumen de progreso
    _summ = _tsumm(t)
    _stat_chips(
        (f"{_summ['played']} jugados", "green", "✅"),
        (f"{_summ['pending']} pendientes", "orange", "⏳"),
        (f"Campeón: {_summ['champion']}" if _summ['champion'] else "Sin campeón aún",
         "green" if _summ['champion'] else "red", "🏆"),
    )

    _tr_div_keys = list(getattr(t, "divisions", []) or [])
    _tr_multi = len(_tr_div_keys) > 1
    _, _tr_div_labels = _division_option_maps()

    # Banner(es) de campeón — por división si es multi-categoría
    from src.tournament_results import champions_by_division as _tchamps
    if _tr_multi:
        _champs = _tchamps(t)
        _champ_cards = [(k, v) for k, v in _champs.items() if v]
        if _champ_cards:
            _cards_html = "".join(
                f'<div style="flex:1;min-width:200px;background:linear-gradient(135deg,#1a0533,#6a1b9a);'
                f'border:2px solid #ffd700;border-radius:14px;padding:1rem;text-align:center">'
                f'<div style="color:#ffd700;font-size:.68rem;font-weight:800;letter-spacing:.1em">'
                f'🏆 {escape(_tr_div_labels.get(k, k))}</div>'
                f'<div style="color:#fff;font-size:1.15rem;font-weight:900;margin-top:.25rem">{escape(v)}</div></div>'
                for k, v in _champ_cards
            )
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:.7rem;margin:1rem 0">{_cards_html}</div>',
                        unsafe_allow_html=True)
    elif _summ["champion"]:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1a0533,#6a1b9a);'
            f'border:2px solid #ffd700;border-radius:16px;padding:1.2rem 1.6rem;margin:1rem 0;'
            f'text-align:center"><div style="color:#ffd700;font-size:.8rem;font-weight:800;'
            f'letter-spacing:.1em">🏆 CAMPEÓN DEL TORNEO</div>'
            f'<div style="color:#fff;font-size:1.5rem;font-weight:900;margin-top:.3rem">'
            f'{escape(_summ["champion"])}</div></div>',
            unsafe_allow_html=True,
        )

    # Partidos jugables (ambas parejas conocidas), ordenados por ronda
    _playable = sorted(
        [m for m in t.matches if m.pair_1 and m.pair_2],
        key=lambda m: (m.round.order, m.match_number),
    )

    if not _playable:
        st.info("Aún no hay partidos con ambas parejas definidas. "
                "En formato grupos+cuadro, juega primero la fase de grupos.")

    # Agrupar: división (si multi) → ronda
    def _render_match_row(m):
            _c1, _c2, _c3 = st.columns([3, 2, 1])
            with _c1:
                _status_icon = "✅" if m.is_played else "⏳"
                st.markdown(
                    f"{_status_icon} **{escape(m.pair_1.display_name)}**  vs  "
                    f"**{escape(m.pair_2.display_name)}**"
                )
                if m.is_played and m.score:
                    st.caption(f"Resultado: {escape(m.score)}")
            with _c2:
                _winner_opts = ["— Sin jugar —", m.pair_1.display_name, m.pair_2.display_name]
                _cur_idx = 0
                if m.winner_id == m.pair_1.id:
                    _cur_idx = 1
                elif m.winner_id == m.pair_2.id:
                    _cur_idx = 2
                _sel = st.selectbox(
                    "Ganador", _winner_opts, index=_cur_idx,
                    key=f"twin_{m.id}", label_visibility="collapsed",
                )
            with _c3:
                _score = st.text_input(
                    "Marcador", value=m.score, key=f"tscore_{m.id}",
                    placeholder="6-4 6-3", label_visibility="collapsed",
                )

            # Aplicar cambios inmediatamente al detectar selección
            _new_winner_id = None
            if _sel == m.pair_1.display_name:
                _new_winner_id = m.pair_1.id
            elif _sel == m.pair_2.display_name:
                _new_winner_id = m.pair_2.id

            if _new_winner_id != m.winner_id or (m.is_played and _score != m.score):
                if _new_winner_id is None and m.is_played:
                    _tclear(t, m.id)
                    st.session_state["tournament"] = t
                    _persist_tournament(t)
                    st.rerun()
                elif _new_winner_id is not None:
                    _treg(t, m.id, _new_winner_id, _score)
                    st.session_state["tournament"] = t
                    _persist_tournament(t)
                    st.rerun()

    if _tr_multi:
        # Agrupar por división, y dentro por ronda
        _by_div = {}
        for m in _playable:
            _by_div.setdefault(m.division, []).append(m)
        for _dk in _tr_div_keys:
            _dms = _by_div.get(_dk, [])
            if not _dms:
                continue
            st.markdown(
                f'<div style="margin:1.2rem 0 .3rem;padding:.5rem .9rem;border-radius:10px;'
                f'background:#0b1a2b;color:#fff;font-weight:800;font-size:.95rem">'
                f'🎾 {escape(_tr_div_labels.get(_dk, _dk))}</div>',
                unsafe_allow_html=True,
            )
            _dr = {}
            for m in _dms:
                _dr.setdefault(m.round, []).append(m)
            for _rnd in sorted(_dr.keys(), key=lambda r: r.order):
                st.caption(_rnd.display)
                for m in _dr[_rnd]:
                    _render_match_row(m)
    else:
        _by_round = {}
        for m in _playable:
            _by_round.setdefault(m.round, []).append(m)
        for _rnd in sorted(_by_round.keys(), key=lambda r: r.order):
            _section_start("🎾", _rnd.display)
            for m in _by_round[_rnd]:
                _render_match_row(m)

    st.divider()
    _t_nav_buttons(5)


# ---------------------------------------------------------------------------
# TORNEO — PASO 6: Exportar
# ---------------------------------------------------------------------------

elif page == "t_export":
    _t_header(6, "Exportar", "Descarga el Excel completo del torneo")
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
            _div_keys, _div_labels = _division_option_maps()
            _div_set = set(_div_keys)
            _divs = [d for d in (getattr(t, "divisions", []) or []) if d in _div_set]
            if not _divs:
                _legacy_div = _legacy_division_key(t)
                if _legacy_div:
                    _divs = [_legacy_div]
            _div_txt = ", ".join(_div_labels.get(d, d) for d in _divs) if _divs else "Abierta"
            _r_data = [
                ("Torneo",       t.name),
                ("TOP",          "⭐ SÍ" if getattr(t, "is_top", False) else "No"),
                ("Categorías",   _div_txt),
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

    _t_nav_buttons(6)


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
                        st.session_state["superadmin_selected_club_id"] = _created["id"]
                        st.session_state["superadmin_selected_club_name"] = _created["name"]
                        st.session_state["_active_club_id"] = _created["id"]
                        _reset_club_runtime_state()
                        st.success(f"✅ Club '{_created['name']}' creado (ID: {_created['id']})")
                        st.rerun()
                    except Exception as _ex:
                        st.error(f"Error al crear el club: {_ex}")

    # ── Tab Usuarios ───────────────────────────────────────────────────────
    with tab_users:
        from src.auth import hash_password as _hash_pw

        st.markdown("### Usuarios del sistema")
        _users_list = _db.list_users()
        _clubs_for_select = _db.list_clubs()
        _club_id_to_name = {c["id"]: c["name"] for c in _clubs_for_select}
        if _users_list:
            # Tabla legible: club por nombre, sin hash, columnas ordenadas
            _rows_u = []
            for _u in _users_list:
                _rows_u.append({
                    "Usuario":     _u.get("username", ""),
                    "Nombre":      _u.get("display_name", ""),
                    "Rol":         _u.get("role", ""),
                    "Club":        _club_id_to_name.get(_u.get("club_id"), "— sin club —"),
                    "Email":       _u.get("email", "") or "—",
                    "Activo":      "✅" if _u.get("is_active", True) else "🚫",
                })
            st.dataframe(pd.DataFrame(_rows_u), use_container_width=True, hide_index=True)
        else:
            st.info("No hay usuarios registrados todavía.")

        _club_map = {"(superadmin — sin club)": None}
        _club_map.update({c["name"]: c["id"] for c in _clubs_for_select})

        # ── Asignar usuario existente a un club (lo primero, es lo más usado) ──
        st.markdown("---")
        st.markdown("#### 🏢 Asignar / mover un usuario a un club")
        if _users_list:
            _users_by_username2 = {u["username"]: u for u in _users_list}
            _mv1, _mv2, _mv3 = st.columns([2, 2, 2])
            with _mv1:
                _mv_username = st.selectbox("Usuario", sorted(_users_by_username2.keys()), key="mv_user")
            _mv_user = _users_by_username2[_mv_username]
            _mv_cur_club = _club_id_to_name.get(_mv_user.get("club_id"), "— sin club —")
            with _mv2:
                _mv_role = st.selectbox(
                    "Rol", ["club_admin", "superadmin"],
                    index=0 if _mv_user.get("role") == "club_admin" else 1, key="mv_role",
                )
            with _mv3:
                _mv_club_labels = list(_club_map.keys())
                _mv_cur_id = _mv_user.get("club_id")
                _mv_vals = list(_club_map.values())
                _mv_idx = _mv_vals.index(_mv_cur_id) if _mv_cur_id in _mv_vals else 0
                _mv_club_label = st.selectbox("Club", _mv_club_labels, index=_mv_idx, key="mv_club")
            _mv_club_id = _club_map[_mv_club_label]
            st.caption(f"Actualmente: **{_mv_user.get('role','?')}** · club **{_mv_cur_club}**")
            if st.button("💾 Guardar club / rol del usuario", type="primary", key="mv_save"):
                if _mv_role == "club_admin" and _mv_club_id is None:
                    st.error("Un club_admin debe estar vinculado a un club. Elige un club o cambia el rol a superadmin.")
                else:
                    try:
                        _db.update_user(
                            _mv_user["id"],
                            role=_mv_role,
                            club_id=None if _mv_role == "superadmin" else _mv_club_id,
                        )
                        st.success(f"✅ '{_mv_username}' ahora es **{_mv_role}**"
                                   + (f" del club **{_mv_club_label}**." if _mv_club_id else " (sin club)."))
                        st.rerun()
                    except Exception as _ex:
                        st.error(f"Error al actualizar: {_ex}")
        else:
            st.info("Crea un usuario primero para poder asignarlo a un club.")

        st.markdown("---")
        st.markdown("#### ➕ Crear nuevo usuario")

        with st.form("form_create_user"):
            _nu_username    = st.text_input("Nombre de usuario", placeholder="club_admin_madrid")
            _nu_display     = st.text_input("Nombre para mostrar", placeholder="Admin Madrid")
            _nu_email       = st.text_input("Email (opcional)", placeholder="admin@padelmadrid.es")
            _nu_password    = st.text_input("Contraseña", type="password")
            _nu_role        = st.selectbox("Rol", ["club_admin", "superadmin"])
            _nu_club_label  = st.selectbox("Club", list(_club_map.keys()))
            _nu_club_id     = _club_map[_nu_club_label]

            if st.form_submit_button("Crear usuario", type="primary"):
                from src.auth import validate_password_strength as _vpw
                _pw_errors = _vpw(_nu_password) if _nu_password else ["La contraseña es obligatoria."]
                if not _nu_username:
                    st.error("El nombre de usuario es obligatorio.")
                elif _pw_errors:
                    for _pwe in _pw_errors:
                        st.error(f"Contraseña: {_pwe}")
                else:
                    try:
                        _db.create_user(
                            username=_nu_username,
                            password_hash=_hash_pw(_nu_password),
                            role=_nu_role,
                            club_id=_nu_club_id,
                            display_name=_nu_display or _nu_username,
                            email=_nu_email,
                        )
                        st.success(f"✅ Usuario **{_nu_username}** ({_nu_role}) creado correctamente.")
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

        # ── Eliminar usuario ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🗑️ Eliminar usuario")
        if _users_list:
            _me = get_session_user() or {}
            _my_id = _me.get("user_id")
            _n_superadmins = sum(1 for u in _users_list if u.get("role") == "superadmin")
            # No permitir borrarse a uno mismo ni dejar el sistema sin superadmin
            _deletable = [u for u in _users_list if u.get("id") != _my_id]
            if not _deletable:
                st.info("No hay otros usuarios que puedas eliminar.")
            else:
                _del_labels = {
                    f'{u["username"]} · {u.get("role","")} · '
                    f'{_club_id_to_name.get(u.get("club_id"), "sin club")}': u
                    for u in _deletable
                }
                _del_choice = st.selectbox("Usuario a eliminar", list(_del_labels.keys()), key="del_user_sel")
                _del_user = _del_labels[_del_choice]
                _is_last_superadmin = (
                    _del_user.get("role") == "superadmin" and _n_superadmins <= 1
                )
                st.warning(f"⚠️ Vas a eliminar **{_del_user['username']}**. Esta acción no se puede deshacer.")
                _del_confirm = st.checkbox(
                    f"Confirmo que quiero eliminar a '{_del_user['username']}'", key="del_user_confirm"
                )
                if _is_last_superadmin:
                    st.error("No puedes eliminar el último superadmin del sistema.")
                if st.button("🗑️ Eliminar usuario definitivamente", type="primary",
                             disabled=(not _del_confirm or _is_last_superadmin), key="del_user_btn"):
                    try:
                        _db.delete_user(_del_user["id"])
                        st.success(f"✅ Usuario '{_del_user['username']}' eliminado.")
                        st.rerun()
                    except Exception as _ex:
                        st.error(f"Error al eliminar el usuario: {_ex}")
        else:
            st.info("No hay usuarios para eliminar.")
