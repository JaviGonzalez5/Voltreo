"""
Voltreo — Vista exclusiva para móvil.

Reglas:
- Sidebar completamente oculto vía CSS + JS
- Navegación en la parte SUPERIOR de cada página (funciona en Streamlit)
- Páginas propias: home, mis torneos, ranking
- Para páginas de desktop: las renderiza el código existente + añade nav arriba
"""
from __future__ import annotations

from html import escape
from typing import Optional
import streamlit as st


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

_CSS = """
<style>
/* ── Ocultar sidebar completamente ── */
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
section[data-testid="stSidebar"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
}
.main, section.main { margin-left: 0 !important; padding-left: 0 !important; }
[data-testid="stAppViewContainer"] { padding-left: 0 !important; margin-left: 0 !important; }
[data-testid="stMainBlockContainer"] { margin-left: 0 !important; }

/* ── Contenido full-width ── */
.main .block-container {
    max-width: 100% !important;
    width: 100% !important;
    margin-left: 0 !important;
    padding-left: .7rem !important;
    padding-right: .7rem !important;
    padding-top: .4rem !important;
    padding-bottom: 1.5rem !important;
}

/* ── Barra de navegación superior ── */
.mob-topnav-bar {
    background: #07111d;
    border-radius: 12px;
    margin-bottom: .9rem;
    padding: .1rem .2rem;
    display: flex;
}
.mob-topnav-bar .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #7a9ec0 !important;
    font-size: .65rem !important;
    font-weight: 800 !important;
    letter-spacing: .05em !important;
    text-transform: uppercase !important;
    padding: .45rem .1rem !important;
    min-height: 48px !important;
    box-shadow: none !important;
    transform: none !important;
    border-radius: 8px !important;
    line-height: 1.2 !important;
}
.mob-topnav-bar .stButton > button:hover,
.mob-topnav-bar .stButton > button:active {
    background: rgba(0,200,83,.15) !important;
    color: #7fffc0 !important;
    box-shadow: none !important;
    transform: none !important;
}
.mob-topnav-bar .mob-active-btn .stButton > button {
    color: #7fffc0 !important;
    background: rgba(0,200,83,.18) !important;
    border-radius: 8px !important;
}

/* ── Cabecera de página ── */
.mob-header {
    padding: .5rem 0 .8rem;
    border-bottom: 2px solid #e2eaf4;
    margin-bottom: .9rem;
}
.mob-header h2 { font-size: 1.15rem; font-weight: 800; color: #07111d; margin: 0; }
.mob-header p  { font-size: .78rem; color: #7f9ab5; margin: .15rem 0 0; }

/* ── Tarjeta ── */
.mob-card {
    background: #fff; border: 1px solid #e2eaf4; border-radius: 12px;
    padding: .85rem 1rem; margin-bottom: .55rem;
    box-shadow: 0 1px 4px rgba(11,26,43,.05);
}
.mob-card-t { font-size: .9rem; font-weight: 700; color: #07111d; }
.mob-card-m { font-size: .76rem; color: #7f9ab5; margin-top: .1rem; }

/* ── Inputs táctiles ── */
.stButton > button { min-height: 44px !important; }
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div { font-size: 16px !important; min-height: 44px !important; }

/* ── Tabs scrollables ── */
[data-testid="stTabs"] [role="tablist"] {
    overflow-x: auto !important; flex-wrap: nowrap !important;
    scrollbar-width: none; -webkit-overflow-scrolling: touch;
}
[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
[data-testid="stTabs"] button[role="tab"] { white-space: nowrap !important; }
[data-testid="stDataFrame"] { overflow-x: auto !important; }

/* ── Banner "Salir de móvil" ── */
.mob-exit-banner {
    text-align: right; margin-bottom: .3rem;
}
</style>
"""

_SIDEBAR_JS = """
<script>
(function(){
    function kill(){
        ['[data-testid="stSidebar"]',
         '[data-testid="collapsedControl"]',
         '[data-testid="stSidebarCollapsedControl"]'].forEach(function(s){
            document.querySelectorAll(s).forEach(function(e){
                e.style.cssText='display:none!important;width:0!important;min-width:0!important;visibility:hidden!important;';
            });
        });
        document.querySelectorAll('.main,section.main').forEach(function(e){
            e.style.marginLeft='0'; e.style.paddingLeft='0';
        });
        var bc=document.querySelector('.main .block-container');
        if(bc){bc.style.marginLeft='0';bc.style.maxWidth='100%';}
    }
    kill();
    new MutationObserver(kill).observe(document.body,{childList:true,subtree:true});
})();
</script>
"""

_RANKING_PAGES = {"config","import","generate","results","standings","export","review","syltek"}
_TORNEO_PAGES  = {"t_config","t_pairs","t_generate","t_schedule","t_results","t_export"}


def _section(page: str) -> str:
    if page in _RANKING_PAGES: return "ranking"
    if page in _TORNEO_PAGES:  return "torneos"
    if page == "club_config":  return "club"
    return "home"


def _go(target: str) -> None:
    st.session_state["_nav_page"] = target
    st.rerun()


def _inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_SIDEBAR_JS, unsafe_allow_html=True)


def _topnav(current: str) -> None:
    """Barra de navegación superior — 4 botones Streamlit reales."""
    sec = _section(current)
    st.markdown('<div class="mob-topnav-bar">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    _btns = [
        (c1, "home",      "🏠\nInicio",  "mob_n_h"),
        (c2, "torneos",   "🏆\nTorneos", "mob_n_t"),
        (c3, "ranking",   "📊\nRanking", "mob_n_r"),
        (c4, "club_config","⚙️\nClub",   "mob_n_c"),
    ]
    for col, key, lbl, k in _btns:
        active = sec == key or (key == "torneos" and sec == "torneos") or \
                 (key == "ranking" and sec == "ranking")
        wrap = "mob-active-btn" if active else ""
        with col:
            st.markdown(f'<div class="{wrap}">', unsafe_allow_html=True)
            if st.button(lbl, key=k, use_container_width=True):
                if key == "torneos": _go("mob_torneos")
                elif key == "ranking": _go("mob_ranking")
                else: _go(key)
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="mob-header"><h2>{escape(title)}</h2>'
        f'{"<p>" + escape(subtitle) + "</p>" if subtitle else ""}</div>',
        unsafe_allow_html=True,
    )


def _prevnext(prev: Optional[str] = None, next_: Optional[str] = None,
              next_lbl: str = "Siguiente →", prev_lbl: str = "← Anterior") -> None:
    c1, c2 = st.columns(2)
    with c1:
        if prev and st.button(prev_lbl, key="mob_prev", use_container_width=True):
            _go(prev)
    with c2:
        if next_ and st.button(next_lbl, key="mob_next",
                               type="primary", use_container_width=True):
            _go(next_)


# ---------------------------------------------------------------------------
# Páginas propias de móvil
# ---------------------------------------------------------------------------

def _page_home(db, s, _db_ok: bool) -> None:
    _header("Panel del club", s.get("club_name") or "")

    # KPIs rápidos
    _t  = s.get("tournament")
    _ph = s.get("phase")
    _groups = list(s.get("groups") or [])
    _pairs  = sum(len(getattr(g, "pairs", []) or []) for g in _groups)
    _sched  = s.get("matches_scheduled", False)

    if _t or _ph or _groups:
        k1, k2, k3 = st.columns(3)
        k1.metric("Grupos", len(_groups))
        k2.metric("Parejas", _pairs)
        k3.metric("Torneo", "✅" if _t else "—")

    st.markdown("---")
    st.markdown("**Accesos rápidos**")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("🏆 Mis Torneos", use_container_width=True, type="primary"):
            _go("mob_torneos")
        if st.button("⚙️ Configurar club", use_container_width=True):
            _go("club_config")
    with a2:
        if st.button("📊 Ranking", use_container_width=True):
            _go("mob_ranking")
        if st.button("➕ Nuevo torneo", use_container_width=True):
            _go("t_config")

    # Salir de modo móvil
    st.markdown(
        '<div class="mob-exit-banner">'
        '<a href="?_mob=0" style="font-size:.72rem;color:#94a8be;text-decoration:none">🖥️ Cambiar a versión escritorio</a>'
        '</div>', unsafe_allow_html=True)


def _page_torneos(db, s, _db_ok: bool) -> None:
    _header("Mis Torneos")

    _t  = s.get("tournament")
    _tid = s.get("db_tournament_id")

    if _db_ok and db is not None:
        from src.auth import current_club_id
        from src.db_converters import tournament_from_db
        _cid = current_club_id()
        if _cid:
            try:
                rows = db.list_tournaments(_cid)
            except Exception:
                rows = []
            if rows:
                for row in rows:
                    active = row["id"] == _tid
                    try:
                        td = tournament_from_db(row)
                        nm = len(getattr(td, "matches", []))
                        played = sum(1 for m in td.matches if getattr(m, "winner_id", None))
                    except Exception:
                        nm = played = 0
                    st.markdown(
                        f'<div class="mob-card" style="{"border-left:3px solid #00c853;" if active else ""}">'
                        f'<div class="mob-card-t">{"✅ " if active else ""}{escape(row.get("name",""))}</div>'
                        f'<div class="mob-card-m">📅 {row.get("start_date","")} · {nm} partidos · {played} jugados</div>'
                        f'</div>', unsafe_allow_html=True)
                    if st.button(f"Abrir →", key=f"mob_t_{row['id']}", use_container_width=True):
                        try:
                            full = db.get_tournament(row["id"], _cid)
                            if full:
                                st.session_state["tournament"] = tournament_from_db(full)
                                st.session_state["db_tournament_id"] = row["id"]
                        except Exception:
                            pass
                        _go("t_config")
            else:
                st.info("No hay torneos. Crea el primero.")
    elif _t:
        st.markdown(
            f'<div class="mob-card" style="border-left:3px solid #00c853">'
            f'<div class="mob-card-t">✅ {escape(_t.name)}</div>'
            f'<div class="mob-card-m">📅 {_t.start_date} · {len(_t.matches)} partidos</div>'
            f'</div>', unsafe_allow_html=True)
        if st.button("Abrir torneo →", use_container_width=True, type="primary"):
            _go("t_config")

    st.markdown("---")
    if st.button("➕ Crear nuevo torneo", type="primary", use_container_width=True):
        _go("t_config")


def _page_ranking(s) -> None:
    _header("Ranking")

    _ph = s.phase
    _steps = [
        ("config",    "1. Configurar",    _ph is not None),
        ("import",    "2. Importar",       s.data_loaded),
        ("generate",  "3. Generar",        s.matches_generated),
        ("results",   "4. Resultados",     bool(getattr(_ph, "match_results", []) if _ph else [])),
        ("standings", "5. Clasificación",  bool(getattr(_ph, "match_results", []) if _ph else [])),
        ("export",    "6. Exportar",       s.matches_scheduled),
    ]
    for key, lbl, done in _steps:
        status = "✅ " if done else ""
        if st.button(f"{status}{lbl}", key=f"mob_rk_{key}", use_container_width=True,
                     type="primary" if not done else "secondary"):
            _go(key)


# ---------------------------------------------------------------------------
# Tablas de navegación ← → por sección
# ---------------------------------------------------------------------------

_NAV = {
    "t_config":   (None,         "t_pairs",    "Siguiente: Parejas →"),
    "t_pairs":    ("t_config",   "t_generate", "Siguiente: Estructura →"),
    "t_generate": ("t_pairs",    "t_schedule", "Siguiente: Horarios →"),
    "t_schedule": ("t_generate", "t_results",  "Siguiente: Resultados →"),
    "t_results":  ("t_schedule", "t_export",   "Siguiente: Exportar →"),
    "t_export":   ("t_results",  None,         ""),
    "config":     (None,         "import",     "Siguiente: Importar →"),
    "import":     ("config",     "generate",   "Siguiente: Generar →"),
    "generate":   ("import",     "export",     "Siguiente: Exportar →"),
    "export":     ("generate",   "review",     "Siguiente: Revisión →"),
    "review":     ("export",     None,         ""),
    "club_config":(None,         None,         ""),
}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def run(db, _db_ok: bool) -> None:
    """
    Llamado desde app.py cuando _is_mobile=True y usuario autenticado.
    Para páginas propias: renderiza y hace st.stop().
    Para páginas de desktop: inyecta solo la nav y deja que desktop renderice.
    """
    _inject()
    s = st.session_state
    page = s.get("_nav_page", "home")

    if page == "mob_torneos":
        _topnav(page)
        _page_torneos(db, s, _db_ok)
        st.stop()

    if page == "mob_ranking":
        _topnav(page)
        _page_ranking(s)
        st.stop()

    if page == "home":
        _topnav(page)
        _page_home(db, s, _db_ok)
        st.stop()

    # Página de desktop: inyectar nav arriba + botones ← → al final
    _topnav(page)
    # Guardar flag para añadir ← → al final de la página de desktop
    s["_mob_prevnext"] = _NAV.get(page, (None, None, ""))
