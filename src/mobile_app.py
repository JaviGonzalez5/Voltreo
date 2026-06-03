"""
Voltreo — Vista exclusiva para móvil.

Completamente separada del código de desktop.
Se activa cuando se detecta un viewport < 768px.
Muestra exactamente el mismo contenido que desktop,
pero con navegación adaptada (botones ← →, menú compacto).
"""
from __future__ import annotations

from html import escape
from datetime import date, datetime
from typing import Optional

import streamlit as st


# ---------------------------------------------------------------------------
# CSS exclusivo del módulo móvil
# ---------------------------------------------------------------------------

_MOB_CSS = """
<style>
/* ── Ocultar sidebar Y su franja colapsada por completo ─── */
[data-testid="stSidebar"]                { display:none!important;width:0!important;min-width:0!important; }
[data-testid="collapsedControl"]         { display:none!important;width:0!important;min-width:0!important; }
[data-testid="stSidebarCollapsedControl"]{ display:none!important;width:0!important; }
section[data-testid="stSidebar"]         { display:none!important;width:0!important; }
/* Quitar TODO el espacio/margen que Streamlit reserva para el sidebar */
.main, section.main                      { margin-left:0!important;padding-left:0!important; }
[data-testid="stAppViewContainer"]       { padding-left:0!important;margin-left:0!important; }
[data-testid="stMainBlockContainer"]     { margin-left:0!important; }
.stApp > * > .main                       { margin-left:0!important; }

/* ── Bloque principal ─── */
.main .block-container {
    max-width: 100% !important;
    padding: .6rem .85rem 5.5rem !important;
    margin-left: 0 !important;
    width: 100% !important;
}

/* ── Barra de navegación inferior fija ─── */
.mob-bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 99999;
    background: #07111d;
    border-top: 1px solid rgba(255,255,255,.10);
    display: flex; justify-content: space-around; align-items: center;
    padding: .4rem .2rem env(safe-area-inset-bottom,.4rem);
    box-shadow: 0 -4px 20px rgba(0,0,0,.4);
}
.mob-bottom-nav .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #4a7aa0 !important;
    font-size: .58rem !important;
    font-weight: 800 !important;
    letter-spacing: .04em !important;
    text-transform: uppercase !important;
    padding: .3rem .2rem !important;
    min-height: 50px !important;
    box-shadow: none !important;
    transform: none !important;
    border-radius: 10px !important;
}
.mob-bottom-nav .stButton > button:active { opacity: .65 !important; background: rgba(0,200,83,.12) !important; }
.mob-bottom-nav .mob-btn-active > button  { color: #7fffc0 !important; background: rgba(0,200,83,.14) !important; }

/* ── Cabecera de sección ─── */
.mob-page-header {
    display: flex; align-items: center; gap: .6rem;
    padding: .6rem 0 .8rem;
    border-bottom: 2px solid #e2eaf4;
    margin-bottom: 1rem;
}
.mob-page-header .mob-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg,#e8f8f0,#d0f2e4);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; flex-shrink: 0;
}
.mob-page-header h1 { font-size: 1.15rem; font-weight: 800; color: #07111d; margin: 0; letter-spacing: -.02em; }
.mob-page-header p  { font-size: .77rem; color: #7f9ab5; margin: .1rem 0 0; }

/* ── Tarjeta de item ─── */
.mob-card {
    background: #fff; border: 1px solid #e2eaf4;
    border-radius: 12px; padding: .9rem 1rem; margin-bottom: .6rem;
    box-shadow: 0 1px 4px rgba(11,26,43,.05);
}
.mob-card-title { font-size: .92rem; font-weight: 700; color: #07111d; margin-bottom: .2rem; }
.mob-card-meta  { font-size: .78rem; color: #7f9ab5; }

/* ── Paso del flujo ─── */
.mob-step-bar {
    display: flex; overflow-x: auto; gap: .3rem; padding: .4rem 0 .6rem;
    scrollbar-width: none; -webkit-overflow-scrolling: touch;
}
.mob-step-bar::-webkit-scrollbar { display: none; }
.mob-step-pill {
    display: inline-flex; align-items: center; gap: .25rem; white-space: nowrap;
    padding: .3rem .7rem; border-radius: 20px; font-size: .72rem; font-weight: 700;
    border: 1px solid #e2eaf4; color: #94a8be; background: #fff; cursor: pointer;
    flex-shrink: 0;
}
.mob-step-pill.done    { background: #e8faf0; border-color: #a8e6c0; color: #005a29; }
.mob-step-pill.active  { background: #07111d; border-color: #00c853; color: #7fffc0; }

/* ── Botones de acción ─── */
.stButton > button { min-height: 44px !important; font-size: .9rem !important; }
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div {
    font-size: 16px !important;
    min-height: 44px !important;
}
[data-testid="stTabs"] [role="tablist"] {
    overflow-x: auto !important; flex-wrap: nowrap !important;
    scrollbar-width: none; -webkit-overflow-scrolling: touch;
}
[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
[data-testid="stTabs"] button[role="tab"] { white-space: nowrap !important; }
[data-testid="stDataFrame"] { overflow-x: auto !important; }
</style>
"""

# Secciones principales
_SECTIONS = [
    ("home",        "🏠", "Inicio"),
    ("torneos",     "🏆", "Torneos"),
    ("ranking",     "📊", "Ranking"),
    ("club_config", "⚙️", "Club"),
]

# Páginas de cada sección
_RANKING_PAGES  = ["config", "import", "generate", "results", "standings", "export", "review", "syltek"]
_TORNEO_PAGES   = ["t_config", "t_pairs", "t_generate", "t_schedule", "t_results", "t_export"]


def _current_section(page: str) -> str:
    if page in _RANKING_PAGES:  return "ranking"
    if page in _TORNEO_PAGES:   return "torneos"
    if page == "club_config":   return "club_config"
    return "home"


def _nav_to(target: str) -> None:
    st.session_state["_nav_page"] = target
    st.rerun()


def _inject_styles() -> None:
    st.markdown(_MOB_CSS, unsafe_allow_html=True)


def _page_header(icon: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="mob-page-header">'
        f'<div class="mob-icon">{icon}</div>'
        f'<div><h1>{escape(title)}</h1>'
        f'{"<p>" + escape(subtitle) + "</p>" if subtitle else ""}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _step_bar(steps: list[tuple[str, str, bool]], current: str) -> None:
    """Barra de pasos scrollable horizontalmente."""
    html = '<div class="mob-step-bar">'
    for key, label, done in steps:
        cls = "active" if key == current else ("done" if done else "")
        html += f'<span class="mob-step-pill {cls}">{escape(label)}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _bottom_nav(current_page: str) -> None:
    """Barra de navegación fija en la parte inferior."""
    section = _current_section(current_page)
    st.markdown('<div class="mob-bottom-nav">', unsafe_allow_html=True)
    cols = st.columns(4)
    defs = [
        ("home",        "🏠", "Inicio",  "mob_bn_home"),
        ("torneos",     "🏆", "Torneos", "mob_bn_torn"),
        ("ranking",     "📊", "Ranking", "mob_bn_rank"),
        ("club_config", "⚙️", "Club",    "mob_bn_club"),
    ]
    for i, (key, icon, label, btn_key) in enumerate(defs):
        active_cls = "mob-btn-active" if section == key else ""
        with cols[i]:
            st.markdown(f'<div class="{active_cls}">', unsafe_allow_html=True)
            if st.button(f"{icon}\n{label}", key=btn_key, use_container_width=True):
                if key == "torneos":   _nav_to("mob_torneos")
                elif key == "ranking": _nav_to("mob_ranking")
                else:                  _nav_to(key)
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _prev_next(prev_page: Optional[str] = None,
               next_page: Optional[str] = None,
               next_label: str = "Siguiente →",
               prev_label: str = "← Anterior") -> None:
    """Botones de navegación anterior / siguiente."""
    c1, c2 = st.columns(2)
    with c1:
        if prev_page and st.button(prev_label, key="mob_prev", use_container_width=True):
            _nav_to(prev_page)
    with c2:
        if next_page and st.button(next_label, key="mob_next",
                                   type="primary", use_container_width=True):
            _nav_to(next_page)


# ---------------------------------------------------------------------------
# Páginas móviles
# ---------------------------------------------------------------------------

def _page_home(db, s) -> None:
    from src.branding import BRAND_NAME, BRAND_GRADIENT
    club = s.get("club_name") or "Mi Club"

    # Hero compacto
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#07111d,#0d2b37);'
        f'border-radius:14px;padding:1.1rem 1.2rem;margin-bottom:1rem">'
        f'<div style="font-size:.65rem;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:#00c853;margin-bottom:.35rem">✦ VOLTREO</div>'
        f'<div style="color:#fff;font-size:1.15rem;font-weight:800;letter-spacing:-.01em">'
        f'{escape(club)}</div>'
        f'<div style="color:rgba(255,255,255,.55);font-size:.8rem;margin-top:.2rem">'
        f'Panel de control</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Tarjetas de acceso rápido — diseño tipo app
    st.markdown(
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.8rem">',
        unsafe_allow_html=True,
    )
    _cards = [
        ("mob_torneos", "🏆", "Torneos",       "#0b1a2b", "#00c853", "Ver y gestionar torneos"),
        ("mob_ranking",  "📊", "Ranking",       "#0b1a2b", "#1565c0", "Fases y clasificación"),
        ("club_config",  "⚙️", "Club",          "#0b1a2b", "#6a1b9a", "Configuración del club"),
        ("t_config",     "➕", "Nuevo torneo",  "#0b1a2b", "#00897b", "Crear un torneo nuevo"),
    ]
    for key, icon, label, bg, accent, desc in _cards:
        st.markdown(
            f'<div style="background:{bg};border:1px solid rgba(255,255,255,.08);'
            f'border-left:3px solid {accent};border-radius:12px;padding:.9rem .9rem .75rem;'
            f'cursor:pointer">'
            f'<div style="font-size:1.4rem;margin-bottom:.3rem">{icon}</div>'
            f'<div style="color:#fff;font-weight:700;font-size:.88rem">{label}</div>'
            f'<div style="color:rgba(255,255,255,.45);font-size:.72rem;margin-top:.1rem">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Botones reales superpuestos (invisibles visualmente, funcionales)
    st.markdown(
        '<style>.mob-grid-btns .stButton>button{background:transparent!important;'
        'border:none!important;height:80px!important;color:transparent!important;'
        'font-size:0!important;margin-top:-88px;opacity:0;position:relative;z-index:10}'
        '</style><div class="mob-grid-btns">',
        unsafe_allow_html=True,
    )
    _g1, _g2 = st.columns(2)
    with _g1:
        if st.button("Torneos",  key="mob_h_torn", use_container_width=True): _nav_to("mob_torneos")
        if st.button("Club",     key="mob_h_club", use_container_width=True): _nav_to("club_config")
    with _g2:
        if st.button("Ranking",  key="mob_h_rank", use_container_width=True): _nav_to("mob_ranking")
        if st.button("Nuevo",    key="mob_h_new",  use_container_width=True): _nav_to("t_config")
    st.markdown("</div>", unsafe_allow_html=True)


def _page_torneos(db, s, _db_ok) -> None:
    """Lista de torneos del club — equivale a la página de torneos en desktop."""
    _page_header("🏆", "Torneos", "Tus torneos activos")

    # Cargar torneos desde BD si hay conexión
    _t = s.get("tournament")
    _tid = s.get("db_tournament_id")

    if _db_ok and db is not None:
        from src.auth import current_club_id
        from src.db_converters import tournament_from_db
        _cid = current_club_id()
        if _cid:
            try:
                _rows = db.list_tournaments(_cid)
            except Exception:
                _rows = []
            if _rows:
                for row in _rows:
                    _active = row["id"] == _tid
                    _n_matches = 0
                    try:
                        _td = tournament_from_db(row)
                        _n_matches = len(getattr(_td, "matches", []))
                    except Exception:
                        pass
                    st.markdown(
                        f'<div class="mob-card" style="{"border-left:3px solid #00c853;" if _active else ""}">'
                        f'<div class="mob-card-title">{"✅ " if _active else ""}{ escape(row.get("name","")) }</div>'
                        f'<div class="mob-card-meta">📅 {row.get("start_date","")} · {_n_matches} partidos</div>'
                        f'</div>', unsafe_allow_html=True)
                    if st.button("Abrir torneo", key=f"mob_open_t_{row['id']}", use_container_width=True):
                        try:
                            _full = db.get_tournament(row["id"], _cid)
                            if _full:
                                st.session_state["tournament"] = tournament_from_db(_full)
                                st.session_state["db_tournament_id"] = row["id"]
                        except Exception:
                            pass
                        _nav_to("t_config")
            else:
                st.info("No hay torneos. Crea el primero.")
    elif _t:
        st.markdown(
            f'<div class="mob-card" style="border-left:3px solid #00c853">'
            f'<div class="mob-card-title">✅ {escape(_t.name)}</div>'
            f'<div class="mob-card-meta">📅 {_t.start_date} · {len(_t.matches)} partidos</div>'
            f'</div>', unsafe_allow_html=True)
        if st.button("Abrir torneo", key="mob_open_cur", use_container_width=True):
            _nav_to("t_config")

    st.markdown("---")
    if st.button("➕ Crear nuevo torneo", type="primary", use_container_width=True):
        _nav_to("t_config")


def _page_ranking(db, s, _db_ok) -> None:
    """Acceso rápido al ranking — mismas opciones que desktop."""
    _page_header("📊", "Ranking", "Gestión del ranking del club")

    _steps = [
        ("config",    "1. Configurar",   s.phase is not None),
        ("import",    "2. Importar",      s.data_loaded),
        ("generate",  "3. Calendario",    s.matches_generated),
        ("results",   "4. Resultados",    bool(getattr(s.phase, "match_results", []) if s.phase else [])),
        ("standings", "5. Clasificación", bool(getattr(s.phase, "match_results", []) if s.phase else [])),
        ("export",    "6. Exportar",      s.matches_scheduled),
    ]
    _step_bar([(k, l, d) for k, l, d in _steps], "ranking")

    st.markdown("**¿Por dónde quieres ir?**")
    for key, label, done in _steps:
        status = "✅ " if done else ""
        if st.button(f"{status}{label}", key=f"mob_r_{key}", use_container_width=True):
            _nav_to(key)


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def run(db, _db_ok: bool) -> None:
    """
    Punto de entrada de la vista móvil.
    Se llama desde app.py cuando se detecta móvil y el usuario está autenticado.
    Llama a st.stop() al final para que app.py no ejecute nada más.
    """
    _inject_styles()

    s = st.session_state
    page = s.get("_nav_page", "home")

    # Páginas móviles propias
    if page == "mob_torneos":
        _page_torneos(db, s, _db_ok)
        _bottom_nav(page)
        st.stop()

    if page == "mob_ranking":
        _page_ranking(db, s, _db_ok)
        _bottom_nav(page)
        st.stop()

    if page == "home":
        _page_home(db, s)
        _bottom_nav(page)
        st.stop()

    # Para todas las demás páginas (las de desktop: t_config, t_pairs, config,
    # import, etc.) dejamos que el código de desktop las renderice,
    # pero AÑADIMOS la barra de navegación inferior y los botones ← →
    # sin tocar nada del código de desktop.
    _add_nav_to_desktop_page(page)


def _add_nav_to_desktop_page(page: str) -> None:
    """
    Para las páginas de desktop, inyectamos:
    1. CSS que oculta el sidebar
    2. La barra inferior de navegación móvil
    Sin tocar el código de renderizado de desktop.
    """
    # La barra inferior se renderizará al final de la página de desktop.
    # Guardamos en session_state para que la función _render_mobile_bottom_nav_footer()
    # la muestre al final (ver app.py).
    st.session_state["_mob_show_bottom_nav"] = True
