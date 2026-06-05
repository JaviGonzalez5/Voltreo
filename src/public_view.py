"""
Vista pública (solo lectura) de un torneo, compartible por enlace.

No requiere login. Renderiza, por categoría: campeón, cuadro por rondas con
resultados, y calendario. Usa el id (UUID) del torneo como "enlace secreto".
"""
from html import escape

import streamlit as st

from .db import get_db, is_db_configured
from .db_converters import tournament_from_db
from .tournament_models import MatchRound, TMatchStatus
from .tournament_results import champions_by_division
from .branding import BRAND_NAME, BRAND_MONOGRAM, BRAND_GRADIENT


_PUBLIC_CSS = f"""
<style>
/* ── Ocultar chrome de Streamlit ── */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="collapsedControl"], .stDeployButton,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}
header[data-testid="stHeader"] {{ display: none !important; }}

/* ── Base ── */
.stApp {{ background: #f4f6f9 !important; }}
.main .block-container {{
    max-width: 860px !important;
    padding: 0 1.2rem 3rem !important;
}}

/* ── Top bar ── */
.pv-topbar {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 1rem 0 1.2rem; margin-bottom: .2rem;
    border-bottom: 1px solid #e5e7eb;
}}
.pv-logo-wrap {{
    display: flex; align-items: center; gap: .65rem;
}}
.pv-logo {{
    width: 36px; height: 36px; border-radius: 10px;
    background: {BRAND_GRADIENT};
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 900; font-size: 1.15rem;
    box-shadow: 0 4px 14px rgba(0,200,83,.35);
}}
.pv-brand-name {{ color: #111827; font-weight: 800; font-size: 1rem; }}
.pv-brand-sub  {{ color: #9ca3af; font-size: .7rem; display: block; }}

/* ── Hero ── */
.pv-hero {{
    background: linear-gradient(135deg, #00c853 0%, #00897b 100%);
    border-radius: 18px; padding: 2rem 2.2rem 1.8rem;
    margin: 1.4rem 0 1.6rem; position: relative; overflow: hidden;
}}
.pv-hero::before {{
    content: ''; position: absolute; right: -40px; top: -40px;
    width: 200px; height: 200px; border-radius: 50%;
    background: rgba(255,255,255,.07);
}}
.pv-hero h1 {{
    color: #fff; font-size: 1.75rem; font-weight: 850;
    margin: 0 0 .9rem; letter-spacing: -.02em;
    text-shadow: 0 2px 8px rgba(0,0,0,.15);
}}
.pv-hero-chips {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
.pv-chip {{
    background: rgba(255,255,255,.2); color: #fff; border-radius: 20px;
    padding: .28rem .75rem; font-size: .82rem; font-weight: 600;
    backdrop-filter: blur(4px);
}}

/* ── Info cards ── */
.pv-info-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: .9rem; margin-bottom: 1.8rem;
}}
.pv-info-card {{
    background: #fff; border-radius: 14px; padding: .9rem 1.1rem;
    border: 1px solid #e9ecef;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
}}
.pv-info-label {{
    font-size: .68rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #9ca3af; margin-bottom: .3rem;
}}
.pv-info-value {{ font-size: .95rem; font-weight: 700; color: #111827; }}
.pv-info-value small {{ font-weight: 400; color: #6b7280; }}

/* ── Section titles ── */
.pv-section-title {{
    font-size: .72rem; font-weight: 800; letter-spacing: .12em;
    text-transform: uppercase; color: #00897b;
    margin: 1.8rem 0 .8rem; padding-bottom: .4rem;
    border-bottom: 2px solid #e5e7eb;
}}

/* ── Division heading ── */
.pv-divh {{
    background: linear-gradient(90deg, #f0fdf4, transparent);
    border-left: 3px solid #00c853; border-radius: 0 8px 8px 0;
    padding: .55rem 1rem; margin: 1.4rem 0 .7rem;
    font-size: .8rem; font-weight: 800; letter-spacing: .08em;
    text-transform: uppercase; color: #065f46;
}}

/* ── Champion ── */
.pv-champ {{
    background: linear-gradient(135deg, #fffbeb, #fef3c7);
    border: 2px solid #f59e0b; border-radius: 14px;
    padding: .85rem 1.2rem; margin: .5rem 0 1rem;
    display: flex; align-items: center; gap: .8rem;
}}
.pv-champ .c1 {{
    font-size: .68rem; font-weight: 800; letter-spacing: .1em;
    text-transform: uppercase; color: #92400e;
}}
.pv-champ .c2 {{ font-size: 1.1rem; font-weight: 900; color: #111827; }}

/* ── Rounds & matches ── */
.pv-round {{
    font-size: .72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .08em; color: #6b7280; margin: 1rem 0 .35rem;
}}
.pv-match {{
    background: #fff; border: 1px solid #e9ecef; border-radius: 10px;
    padding: .65rem 1rem; margin-bottom: .4rem;
    display: flex; align-items: center; justify-content: space-between; gap: .8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}}
.pv-match .pair {{ color: #374151; font-size: .92rem; flex: 1; }}
.pv-match .pair.win {{ color: #059669; font-weight: 700; }}
.pv-match .sc  {{ color: #111827; font-size: .88rem; font-weight: 700; white-space: nowrap; }}
.pv-match .vs  {{ color: #d1d5db; font-size: .78rem; padding: 0 .4rem; }}
.pv-when {{ color: #9ca3af; font-size: .72rem; white-space: nowrap; }}

/* ── Category cards (inscripción) ── */
.pv-cat-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem; margin: 1rem 0 1.6rem;
}}
.pv-cat-card {{
    background: #fff; border: 1px solid #e9ecef; border-radius: 16px;
    padding: 1.2rem 1.3rem; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.06); transition: box-shadow .15s;
}}
.pv-cat-name  {{ font-size: 1rem; font-weight: 800; color: #111827; margin-bottom: .3rem; }}
.pv-cat-count {{ font-size: .82rem; color: #6b7280; margin-bottom: .75rem; }}
.pv-cat-full  {{ font-size: .78rem; color: #dc2626; font-weight: 700; margin-bottom: .75rem; }}
.pv-btn {{
    display: inline-block; background: linear-gradient(135deg, #00c853, #00897b);
    color: #fff !important; border-radius: 30px; padding: .5rem 1.4rem;
    font-size: .88rem; font-weight: 700; text-decoration: none;
    box-shadow: 0 3px 10px rgba(0,200,83,.3); cursor: pointer;
}}
.pv-btn-full {{
    display: inline-block; background: #f3f4f6; color: #9ca3af !important;
    border-radius: 30px; padding: .5rem 1.4rem;
    font-size: .88rem; font-weight: 700; cursor: default;
}}

/* ── Status badge ── */
.pv-badge-open {{
    display: inline-flex; align-items: center; gap: .4rem;
    background: #d1fae5; color: #065f46; border-radius: 20px;
    padding: .35rem 1rem; font-size: .82rem; font-weight: 700;
    margin-bottom: 1.2rem;
}}
.pv-badge-closed {{
    display: inline-flex; align-items: center; gap: .4rem;
    background: #fee2e2; color: #991b1b; border-radius: 20px;
    padding: .35rem 1rem; font-size: .82rem; font-weight: 700;
    margin-bottom: 1.2rem;
}}

/* ── Form styles ── */
.pv-form-section {{
    background: #fff; border-radius: 16px; padding: 1.4rem 1.6rem;
    border: 1px solid #e9ecef; margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
}}
.pv-form-title {{
    font-size: .72rem; font-weight: 800; letter-spacing: .1em;
    text-transform: uppercase; color: #00897b; margin-bottom: .9rem;
    padding-bottom: .5rem; border-bottom: 1px solid #f0fdf4;
}}

/* ── Streamlit widget overrides (form) ── */
[data-testid="stForm"] {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}
[data-testid="stForm"] label,
[data-testid="stForm"] [data-testid="stWidgetLabel"] p {{
    color: #374151 !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
}}
[data-testid="stForm"] p,
[data-testid="stForm"] div.stMarkdown p {{
    color: #374151 !important;
}}
[data-testid="stForm"] [data-testid="stCaptionContainer"] p {{
    color: #9ca3af !important;
}}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
    background: #f9fafb !important;
    border: 1.5px solid #e5e7eb !important;
    border-radius: 10px !important;
    color: #111827 !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: #00c853 !important;
    box-shadow: 0 0 0 3px rgba(0,200,83,.12) !important;
}}
[data-testid="stSelectbox"] > div > div {{
    background: #f9fafb !important;
    border: 1.5px solid #e5e7eb !important;
    border-radius: 10px !important;
    color: #111827 !important;
}}
div[data-testid="stFormSubmitButton"] > button {{
    background: linear-gradient(135deg, #00c853, #00897b) !important;
    color: #fff !important; border: none !important;
    border-radius: 30px !important; font-weight: 700 !important;
    font-size: 1rem !important; padding: .75rem 1.5rem !important;
    box-shadow: 0 4px 14px rgba(0,200,83,.35) !important;
}}
hr {{ border-color: #f0f0f0 !important; margin: .8rem 0 !important; }}

/* ── Botón "Inscribirse" dentro de cada card de categoría ── */
div[data-testid="stButton"] > button.pv-cat-btn {{
    background: linear-gradient(135deg, #00c853, #00897b) !important;
    color: #fff !important; border: none !important;
    border-radius: 30px !important; font-weight: 700 !important;
    font-size: .88rem !important; padding: .45rem 1.2rem !important;
    box-shadow: 0 3px 10px rgba(0,200,83,.3) !important;
    width: 100% !important;
}}
/* Botón "← Volver" */
div[data-testid="stButton"] > button.pv-back-btn {{
    background: #f3f4f6 !important; color: #374151 !important;
    border: 1.5px solid #e5e7eb !important; border-radius: 30px !important;
    font-weight: 600 !important; font-size: .88rem !important;
}}
/* Aplicar estilo verde a TODOS los st.button dentro del grid de categorías */
.pv-cat-col div[data-testid="stButton"] > button {{
    background: linear-gradient(135deg, #00c853, #00897b) !important;
    color: #fff !important; border: none !important;
    border-radius: 30px !important; font-weight: 700 !important;
    box-shadow: 0 3px 10px rgba(0,200,83,.3) !important;
    width: 100% !important;
}}

/* ── Disponibilidad day header ── */
.pv-day-header {{
    background: #f0fdf4; border-left: 4px solid #00c853;
    border-radius: 0 10px 10px 0; padding: .55rem 1rem;
    font-weight: 700; font-size: .95rem; color: #065f46;
    margin: .8rem 0 .4rem;
}}

/* ── Footer ── */
.pv-foot {{
    text-align: center; color: #9ca3af; font-size: .78rem;
    margin: 2.5rem 0 1rem; padding-top: 1.2rem;
    border-top: 1px solid #e9ecef;
}}
.pv-foot a {{ color: #00897b; text-decoration: none; font-weight: 600; }}

/* ── Móvil ── */
@media (max-width: 640px) {{
    .main .block-container {{
        padding: 0 .7rem 2rem !important;
    }}
    .pv-hero {{ padding: 1.4rem 1.3rem 1.2rem !important; border-radius: 14px !important; }}
    .pv-hero h1 {{ font-size: 1.35rem !important; }}
    .pv-info-grid {{ grid-template-columns: 1fr 1fr !important; }}
    .pv-cat-grid  {{ grid-template-columns: 1fr 1fr !important; }}
    .pv-form-section {{ padding: 1rem 1rem !important; }}
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stTextArea"] textarea {{
        font-size: 16px !important;
        min-height: 46px !important;
    }}
    .stButton > button {{ min-height: 48px !important; }}
}}
</style>
"""


def _topbar(subtitle: str = "Resultados en directo") -> str:
    return (
        f'<div class="pv-topbar">'
        f'<div class="pv-logo-wrap">'
        f'<div class="pv-logo">{BRAND_MONOGRAM}</div>'
        f'<div><span class="pv-brand-name">{escape(BRAND_NAME)}</span>'
        f'<span class="pv-brand-sub">{subtitle}</span></div>'
        f'</div></div>'
    )


def _fmt_when(m) -> str:
    if not m.match_date:
        return ""
    d = m.match_date.strftime("%d/%m")
    t = m.start_time.strftime("%H:%M") if m.start_time else ""
    court = f" · {m.court.name}" if m.court else ""
    return f"{d} {t}{court}".strip()


def render_public_tournament(tournament_id: str) -> None:
    """Renderiza la vista pública de un torneo y llama a st.stop()."""
    st.markdown(_PUBLIC_CSS, unsafe_allow_html=True)
    st.markdown(_topbar("Resultados en directo"), unsafe_allow_html=True)

    if not is_db_configured():
        st.error("Servicio no disponible.")
        st.stop()

    try:
        row = get_db().get_tournament_public(tournament_id)
    except Exception:
        row = None

    if not row:
        st.markdown(
            '<div class="pv-hero"><h1>Torneo no encontrado</h1>'
            '<div style="color:rgba(255,255,255,.8);margin-top:.5rem">'
            'El enlace no es válido o el torneo ya no está disponible.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    try:
        t = tournament_from_db(row)
    except Exception:
        st.error("No se pudo cargar el torneo.")
        st.stop()

    # Eliminar inscripciones (datos personales: emails, teléfonos, apellidos)
    # antes de renderizar. La vista de resultados solo necesita partidos y grupos.
    t.registrations = []

    # ── Hero ─────────────────────────────────────────────────────────────────
    _dates = t.start_date.strftime("%d/%m/%Y")
    if t.end_date and t.end_date != t.start_date:
        _dates += f" – {t.end_date.strftime('%d/%m/%Y')}"
    _chips = [f"📅 {_dates}"]
    if getattr(t, "location", ""):
        _chips.append(f"📍 {escape(t.location)}")
    _chips_html = "".join(f'<span class="pv-chip">{c}</span>' for c in _chips)

    st.markdown(
        f'<div class="pv-hero">'
        f'<h1>🏆 {escape(t.name)}</h1>'
        f'<div class="pv-hero-chips">{_chips_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Resultados por división ───────────────────────────────────────────────
    div_keys = sorted({m.division for m in t.matches if m.division is not None})
    champs = champions_by_division(t)

    def _render_division(div_key, label):
        if label:
            st.markdown(f'<div class="pv-divh">{escape(label)}</div>', unsafe_allow_html=True)
        champ = champs.get(div_key or "_")
        if champ:
            st.markdown(
                f'<div class="pv-champ"><span style="font-size:1.5rem">🏆</span>'
                f'<div><div class="c1">Campeón</div><div class="c2">{escape(champ)}</div></div></div>',
                unsafe_allow_html=True,
            )
        dms = [m for m in t.matches if (div_key is None or m.division == div_key)]
        by_round = {}
        for m in dms:
            by_round.setdefault(m.round, []).append(m)
        for rnd in sorted(by_round.keys(), key=lambda r: r.order):
            visible = [m for m in by_round[rnd] if m.pair_1 or m.pair_2]
            if not visible:
                continue
            st.markdown(f'<div class="pv-round">{escape(rnd.display)}</div>', unsafe_allow_html=True)
            for m in sorted(visible, key=lambda x: x.match_number):
                p1cls = "pair win" if (m.winner_id and m.pair_1 and m.winner_id == m.pair_1.id) else "pair"
                p2cls = "pair win" if (m.winner_id and m.pair_2 and m.winner_id == m.pair_2.id) else "pair"
                p1 = escape(m.p1_display); p2 = escape(m.p2_display)
                sc = escape(m.score) if m.score else ("✓" if m.winner_id else "")
                when = _fmt_when(m)
                when_html = f'<span class="pv-when">{escape(when)}</span>' if when else ""
                st.markdown(
                    f'<div class="pv-match">'
                    f'<span class="{p1cls}">{p1}</span>'
                    f'<span class="vs">vs</span>'
                    f'<span class="{p2cls}" style="text-align:right">{p2}</span>'
                    f'<span class="sc">{sc}</span>{when_html}</div>',
                    unsafe_allow_html=True,
                )

    if div_keys:
        from .tournament_models import TournamentCategory, TournamentSubcategory
        def _label(k):
            cat, _, sub = k.partition(":")
            c = next((x for x in TournamentCategory if x.value == cat), None)
            s = next((x for x in TournamentSubcategory if x.value == sub), None)
            return " ".join([p for p in [c.label if c else "", s.label if s else ""] if p]) or k
        st.markdown('<div class="pv-section-title">Resultados</div>', unsafe_allow_html=True)
        for dk in div_keys:
            _render_division(dk, _label(dk))
    else:
        _render_division(None, "")

    st.markdown(
        f'<div class="pv-foot">Organizado con <a href="https://{BRAND_NAME.lower()}.streamlit.app">'
        f'{escape(BRAND_NAME)}</a> · Gestión de torneos y rankings deportivos</div>',
        unsafe_allow_html=True,
    )
    st.stop()


def render_public_registration(tournament_id: str) -> None:
    """
    Página pública de inscripción — flujo en 2 pasos:
      Paso 1: info del torneo + grid de categorías
      Paso 2: formulario para la categoría elegida
    """
    from datetime import datetime as _dtt
    from .tournament_models import TournamentRegistration, RegistrationStatus

    st.markdown(_PUBLIC_CSS, unsafe_allow_html=True)

    if not is_db_configured():
        st.error("Servicio no disponible.")
        st.stop()

    try:
        row = get_db().get_tournament_public(tournament_id)
    except Exception:
        row = None

    if not row:
        st.markdown(_topbar("Inscripción en torneo"), unsafe_allow_html=True)
        st.markdown(
            '<div class="pv-hero"><h1>Torneo no encontrado</h1>'
            '<div style="color:rgba(255,255,255,.8);margin-top:.5rem">'
            'El enlace no es válido o el torneo ya no está disponible.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    try:
        from .db_converters import tournament_from_db as _tfdb
        t = _tfdb(row)
    except Exception:
        st.error("No se pudo cargar el torneo.")
        st.stop()

    # ── Labels de categorías ──────────────────────────────────────────────────
    _div_keys  = list(getattr(t, "divisions", []) or [])
    _div_labels: dict = {}
    try:
        from .tournament_models import TournamentCategory, TournamentSubcategory
        for k in _div_keys:
            cat_v, _, sub_v = k.partition(":")
            c = next((x for x in TournamentCategory  if x.value == cat_v), None)
            s = next((x for x in TournamentSubcategory if x.value == sub_v), None)
            _div_labels[k] = " ".join([p for p in [c.label if c else "", s.label if s else ""] if p]) or k
    except Exception:
        pass
    _max_pairs = getattr(t, "registration_max_pairs", {}) or {}

    # ── Hero (común a ambos pasos) ────────────────────────────────────────────
    _dates = t.start_date.strftime("%d/%m/%Y")
    if t.end_date and t.end_date != t.start_date:
        _dates += f" – {t.end_date.strftime('%d/%m/%Y')}"
    _chips = [f"📅 {_dates}"]
    if getattr(t, "location", ""):
        _chips.append(f"📍 {escape(t.location)}")
    _chips_html = "".join(f'<span class="pv-chip">{c}</span>' for c in _chips)

    # ── Estado de navegación: categoría seleccionada ──────────────────────────
    _sel_key = f"_reg_cat_{tournament_id}"
    _selected_cat: str | None = st.session_state.get(_sel_key)

    # Parejas confirmadas por categoría (disponible en ambos pasos)
    _pairs_by_cat: dict = {}
    for _pp in getattr(t, "pairs", []) or []:
        _pk = getattr(_pp, "division", None) or "_"
        _pairs_by_cat.setdefault(_pk, []).append(_pp)

    # ════════════════════════════════════════════════════════════════════════
    # PASO 1 — Presentación del torneo + grid de categorías
    # ════════════════════════════════════════════════════════════════════════
    if _selected_cat is None:
        st.markdown(_topbar("Inscripción en torneo"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="pv-hero"><h1>🎾 {escape(t.name)}</h1>'
            f'<div class="pv-hero-chips">{_chips_html}</div></div>',
            unsafe_allow_html=True,
        )

        if not t.is_registration_active():
            st.markdown('<div class="pv-badge-closed">🔒 Inscripciones cerradas</div>',
                        unsafe_allow_html=True)
            st.info("El club aún no ha abierto el registro. Contacta con los organizadores.")
            st.stop()

        st.markdown('<div class="pv-badge-open">✅ Inscripciones abiertas</div>',
                    unsafe_allow_html=True)

        if _div_keys:
            st.markdown('<div class="pv-section-title">Categorías — elige la tuya</div>',
                        unsafe_allow_html=True)
            _cols_per_row = 4
            for _row_start in range(0, len(_div_keys), _cols_per_row):
                _row_keys = _div_keys[_row_start: _row_start + _cols_per_row]
                _rcols = st.columns(len(_row_keys))
                for _ci, _dk in enumerate(_row_keys):
                    _mx   = _max_pairs.get(_dk, 0)
                    _cnt  = t.confirmed_count(_dk)
                    _lbl  = _div_labels.get(_dk, _dk)
                    _full = bool(_mx and _cnt >= _mx)
                    _count_txt = f"{_cnt}/{_mx}" if _mx else str(_cnt)
                    with _rcols[_ci]:
                        st.markdown(
                            f'<div class="pv-cat-card" style="min-height:110px">'
                            f'<div class="pv-cat-name">{escape(_lbl)}</div>'
                            f'<div class="{"pv-cat-full" if _full else "pv-cat-count"}">'
                            f'{"🔴 Completo" if _full else "👥"} {_count_txt} inscritas</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        # Siempre mostrar "Acceder" (completo o no)
                        if st.button("Acceder", key=f"sel_cat_{_dk}",
                                     use_container_width=True):
                            st.session_state[_sel_key] = _dk
                            st.rerun()
        else:
            # Sin categorías: ir directo al formulario sin selección
            st.session_state[_sel_key] = ""
            st.rerun()

        st.markdown(
            f'<div class="pv-foot">Organizado con '
            f'<a href="https://{BRAND_NAME.lower()}.streamlit.app">{escape(BRAND_NAME)}</a></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # ════════════════════════════════════════════════════════════════════════
    # PASO 2 — Formulario de inscripción para la categoría elegida
    # ════════════════════════════════════════════════════════════════════════
    _cat_label = _div_labels.get(_selected_cat, "") if _selected_cat else ""
    _back_sub  = f"← {escape(_cat_label)}" if _cat_label else "← Volver"
    st.markdown(_topbar(_back_sub), unsafe_allow_html=True)

    # Botón volver
    if st.button("← Volver a categorías", key="reg_back"):
        st.session_state.pop(_sel_key, None)
        st.rerun()

    # Hero compacto
    st.markdown(
        f'<div class="pv-hero" style="padding:1.3rem 1.8rem 1.1rem">'
        f'<h1 style="font-size:1.4rem">🎾 {escape(t.name)}</h1>'
        f'<div class="pv-hero-chips">{_chips_html}'
        + (f'<span class="pv-chip" style="background:rgba(255,255,255,.35);font-size:.9rem">'
           f'🏷 {escape(_cat_label)}</span>' if _cat_label else "")
        + f'</div></div>',
        unsafe_allow_html=True,
    )

    if not t.is_registration_active():
        st.markdown('<div class="pv-badge-closed">🔒 Inscripciones cerradas</div>',
                    unsafe_allow_html=True)
        st.stop()

    if st.session_state.get(f"_reg_done_{tournament_id}"):
        st.success("✅ ¡Inscripción enviada! El club revisará tu solicitud y te confirmará.")
        st.caption("Puedes cerrar esta ventana o volver para inscribir otra pareja.")
        if st.button("← Inscribir otra pareja", key="reg_another"):
            st.session_state.pop(_sel_key, None)
            st.session_state.pop(f"_reg_done_{tournament_id}", None)
            st.rerun()
        st.stop()

    # ── Dos pestañas: Inscribirse / Parejas Inscritas ─────────────────────────
    _cat_pairs_step2 = _pairs_by_cat.get(_selected_cat or "_", []) if _selected_cat else []
    _tab_form, _tab_list = st.tabs(["📝 Inscribirse", f"👥 Parejas Inscritas ({len(_cat_pairs_step2)})"])

    with _tab_list:
        if not _cat_pairs_step2:
            st.info("Todavía no hay parejas inscritas en esta categoría. ¡Sé el primero!")
        else:
            st.markdown('<div class="pv-section-title">Parejas confirmadas</div>',
                        unsafe_allow_html=True)
            for _i, _cp in enumerate(_cat_pairs_step2, 1):
                _p1 = getattr(_cp, "player_1", None)
                _p2 = getattr(_cp, "player_2", None)
                _p1_full = " ".join(filter(None, [
                    getattr(_p1, "name", ""),
                    getattr(_p1, "surname", ""),
                ])) if _p1 else ""
                _p2_full = " ".join(filter(None, [
                    getattr(_p2, "name", ""),
                    getattr(_p2, "surname", ""),
                ])) if _p2 else ""
                st.markdown(
                    f'<div style="background:#fff;border:1px solid #e9ecef;border-radius:12px;'
                    f'padding:.8rem 1.1rem;margin-bottom:.5rem">'
                    f'<div style="font-weight:700;color:#111827;font-size:.95rem">'
                    f'{_i}. {escape(_cp.name or "—")}</div>'
                    f'<div style="color:#6b7280;font-size:.82rem;margin-top:.2rem">'
                    f'👤 {escape(_p1_full or getattr(_p1,"name","") or "—")} &nbsp;·&nbsp; '
                    f'👤 {escape(_p2_full or getattr(_p2,"name","") or "—")}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    with _tab_form:
        if not t.is_registration_active():
            st.markdown('<div class="pv-badge-closed">🔒 Inscripciones cerradas</div>',
                        unsafe_allow_html=True)
            st.info("El club aún no ha abierto el registro. Contacta con los organizadores.")
        else:
            st.markdown('<div class="pv-section-title">Formulario de inscripción</div>',
                        unsafe_allow_html=True)

            # — Variables de disponibilidad (se rellenan dentro del form) —
            _ask_avail = getattr(t, "registration_ask_availability", False)

            with st.form("public_registration_form"):
                div_sel_key = _selected_cat if _selected_cat else None
                if _cat_label:
                    st.markdown(
                        f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;'
                        f'border-radius:10px;padding:.55rem 1rem;margin-bottom:.8rem;'
                        f'font-weight:700;color:#065f46">🏷 {escape(_cat_label)}</div>',
                        unsafe_allow_html=True,
                    )

                # ── Jugador 1 ─────────────────────────────────────────────
                st.markdown('<div class="pv-form-title">Jugador 1</div>', unsafe_allow_html=True)
                p1_name = st.text_input("Nombre *", key="p1n", placeholder="Carlos")
                _p1s1, _p1s2 = st.columns(2)
                with _p1s1: p1_surname1 = st.text_input("Primer apellido *", key="p1s1", placeholder="García")
                with _p1s2: p1_surname2 = st.text_input("Segundo apellido *", key="p1s2", placeholder="Martínez")
                _p1c1, _p1c2 = st.columns(2)
                with _p1c1: p1_phone = st.text_input("Teléfono *", key="p1ph", placeholder="+34 600 000 000")
                with _p1c2: p1_email = st.text_input("Email *", key="p1em", placeholder="carlos@email.com")

                st.divider()

                # ── Jugador 2 ─────────────────────────────────────────────
                st.markdown('<div class="pv-form-title">Jugador 2</div>', unsafe_allow_html=True)
                p2_name = st.text_input("Nombre *", key="p2n", placeholder="Marta")
                _p2s1, _p2s2 = st.columns(2)
                with _p2s1: p2_surname1 = st.text_input("Primer apellido *", key="p2s1", placeholder="López")
                with _p2s2: p2_surname2 = st.text_input("Segundo apellido *", key="p2s2", placeholder="Fernández")
                _p2c1, _p2c2 = st.columns(2)
                with _p2c1: p2_phone = st.text_input("Teléfono *", key="p2ph", placeholder="+34 600 000 001")
                with _p2c2: p2_email = st.text_input("Email *", key="p2em", placeholder="marta@email.com")

                st.divider()
                notes = st.text_area("Nota para el organizador (opcional)",
                                     placeholder="Cualquier información adicional…", height=70)

                # ── Disponibilidad ────────────────────────────────────────
                unavailable_selected: list[str] = []
                availability_windows: dict      = {}

                if _ask_avail:
                    from datetime import timedelta as _td, time as _time_cls
                    _days_range = []
                    _d = t.start_date
                    while _d <= t.end_date:
                        _days_range.append(_d); _d = _d + _td(days=1)

                    if _days_range:
                        st.divider()
                        st.markdown('<div class="pv-form-title">¿Cuándo puedes jugar?</div>',
                                    unsafe_allow_html=True)
                        st.caption("Indica tu disponibilidad. Si puedes todo el día no hace falta cambiar nada.")

                        def _as_time(val, default):
                            return val if isinstance(val, _time_cls) else default

                        _wk_start = _as_time(getattr(t, "day_start_time", None), _time_cls(9, 0))
                        _wk_end   = _as_time(getattr(t, "day_end_time",   None), _time_cls(22, 0))
                        _we_start = _as_time(getattr(t, "weekend_start_time", None), None) or _wk_start
                        _we_end   = _as_time(getattr(t, "weekend_end_time",   None), None) or _wk_end
                        if _wk_start.hour < 8: _wk_start = _time_cls(9, 0)
                        if _we_start.hour < 8: _we_start = _wk_start

                        def _topts(s, e):
                            opts, h, m = [], s.hour, 0 if s.minute < 30 else 30
                            while True:
                                opts.append(f"{h:02d}:{m:02d}")
                                if h == e.hour and m >= (0 if e.minute < 30 else 30): break
                                m += 30
                                if m >= 60: m, h = 0, h + 1
                                if h > 23 or (h == e.hour and m > e.minute): break
                            end_s = f"{e.hour:02d}:{(0 if e.minute < 30 else 30):02d}"
                            if end_s not in opts: opts.append(end_s)
                            return opts

                        _day_names_full = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                        _seen_wdays: list[int] = []
                        for _dd in _days_range:
                            if _dd.weekday() not in _seen_wdays: _seen_wdays.append(_dd.weekday())

                        for _wday in _seen_wdays:
                            _wkey = str(_wday)
                            _is_we = _wday >= 5
                            _ds, _de = (_we_start, _we_end) if _is_we else (_wk_start, _wk_end)
                            _opts = _topts(_ds, _de)
                            _ss = f"{_ds.hour:02d}:{_ds.minute:02d}"
                            _es = f"{_de.hour:02d}:{_de.minute:02d}"
                            st.markdown(f'<div class="pv-day-header">📅 {_day_names_full[_wday]}</div>',
                                        unsafe_allow_html=True)
                            _cp = st.selectbox("Disponibilidad", ["✅ Puedo jugar", "❌ No puedo jugar"],
                                               key=f"avail_st_{_wkey}", label_visibility="collapsed")
                            if _cp == "❌ No puedo jugar":
                                for _dd2 in _days_range:
                                    if _dd2.weekday() == _wday: unavailable_selected.append(_dd2.isoformat())
                            else:
                                _fc1, _fc2 = st.columns(2)
                                with _fc1:
                                    _fr = st.selectbox("⏩ Desde", _opts,
                                                       index=_opts.index(_ss) if _ss in _opts else 0,
                                                       key=f"avail_from_{_wkey}")
                                with _fc2:
                                    _to = st.selectbox("⏹ Hasta", _opts,
                                                       index=_opts.index(_es) if _es in _opts else len(_opts)-1,
                                                       key=f"avail_to_{_wkey}")
                                if _fr != _ss or _to != _es:
                                    for _dd2 in _days_range:
                                        if _dd2.weekday() == _wday:
                                            availability_windows[_dd2.isoformat()] = {"from": _fr, "to": _to}

                submitted = st.form_submit_button("📩 Enviar inscripción", type="primary",
                                                  use_container_width=True)

            # ── Validación y guardado (fuera del form, dentro del tab) ───
            if submitted:
                errors = []
                if not p1_name.strip():     errors.append("Jugador 1: falta el nombre.")
                if not p1_surname1.strip(): errors.append("Jugador 1: falta el primer apellido.")
                if not p1_surname2.strip(): errors.append("Jugador 1: falta el segundo apellido.")
                if not p1_phone.strip():    errors.append("Jugador 1: falta el teléfono.")
                if not p1_email.strip():    errors.append("Jugador 1: falta el email.")
                if not p2_name.strip():     errors.append("Jugador 2: falta el nombre.")
                if not p2_surname1.strip(): errors.append("Jugador 2: falta el primer apellido.")
                if not p2_surname2.strip(): errors.append("Jugador 2: falta el segundo apellido.")
                if not p2_phone.strip():    errors.append("Jugador 2: falta el teléfono.")
                if not p2_email.strip():    errors.append("Jugador 2: falta el email.")
                if div_sel_key and t.is_division_full(div_sel_key):
                    errors.append("Esta categoría ya está completa. Vuelve y elige otra.")
                for e in errors:
                    st.error(e)
                if not errors:
                    def _short(name: str, surname: str) -> str:
                        n = name.strip(); s = surname.strip()
                        return f"{n[0].upper()}. {s.capitalize()}" if n and s else (s or n)
                    reg = TournamentRegistration(
                        pair_name            = f"{_short(p1_name, p1_surname1)} – {_short(p2_name, p2_surname1)}",
                        player1_name         = p1_name.strip(),
                        player1_surname1     = p1_surname1.strip(),
                        player1_surname2     = p1_surname2.strip(),
                        player1_phone        = p1_phone.strip(),
                        player1_email        = p1_email.strip(),
                        player2_name         = p2_name.strip(),
                        player2_surname1     = p2_surname1.strip(),
                        player2_surname2     = p2_surname2.strip(),
                        player2_phone        = p2_phone.strip(),
                        player2_email        = p2_email.strip(),
                        division             = div_sel_key or None,
                        notes                = notes.strip(),
                        unavailable_dates    = unavailable_selected,
                        availability_windows = availability_windows,
                        status               = RegistrationStatus.PENDING,
                        submitted_at         = _dtt.utcnow().isoformat(),
                    )
                    try:
                        t.registrations.append(reg)
                        from .db_converters import tournament_to_db as _ttdb
                        payload = _ttdb(t, row.get("club_id", ""), t.id)
                        get_db().upsert_tournament(
                            club_id         = row.get("club_id", ""),
                            name            = payload["name"],
                            start_date      = payload["start_date"],
                            end_date        = payload["end_date"],
                            tournament_data = payload["tournament_data"],
                            tournament_id   = t.id,
                        )
                        st.session_state[f"_reg_done_{tournament_id}"] = True
                        # ── Enviar correo de confirmación (opcional) ──────
                        try:
                            from .email_sender import notify_registration_received
                            _p1_full = " ".join(filter(None, [
                                reg.player1_name,
                                reg.player1_surname1,
                                reg.player1_surname2,
                            ]))
                            _p2_full = " ".join(filter(None, [
                                reg.player2_name,
                                reg.player2_surname1,
                                reg.player2_surname2,
                            ]))
                            notify_registration_received(
                                to_emails       = [reg.player1_email, reg.player2_email],
                                tournament_name = t.name,
                                pair_name       = reg.pair_name,
                                category        = _div_labels.get(div_sel_key, "") if div_sel_key else "",
                                player1_full    = _p1_full,
                                player2_full    = _p2_full,
                            )
                        except Exception:
                            pass  # El email es opcional; la inscripción ya está guardada
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Error al guardar la inscripción: {_e}")

    st.markdown(
        f'<div class="pv-foot">Organizado con '
        f'<a href="https://{BRAND_NAME.lower()}.streamlit.app">{escape(BRAND_NAME)}</a></div>',
        unsafe_allow_html=True,
    )
    st.stop()
