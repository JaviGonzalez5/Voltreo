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
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="collapsedControl"], .stDeployButton,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}
header[data-testid="stHeader"] {{ display: none !important; }}
.stApp {{ background: #0a1622 !important; }}
.main .block-container {{ max-width: 1040px !important; padding-top: 2.5rem !important; }}

.pubv-brand {{ display:flex; align-items:center; gap:.7rem; margin-bottom:1.4rem; }}
.pubv-logo {{
    width:40px; height:40px; border-radius:12px; background:{BRAND_GRADIENT};
    display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; font-size:1.3rem;
    box-shadow:0 6px 22px rgba(0,200,83,.4);
}}
.pubv-brand b {{ color:#eaf6ff; font-size:1.05rem; letter-spacing:-.01em; }}
.pubv-brand span {{ color:#4a7aa0; font-size:.68rem; letter-spacing:.16em; text-transform:uppercase; display:block; }}

.pubv-hero {{
    background:linear-gradient(135deg,#07121f,#0d2b37); border:1px solid rgba(255,255,255,.08);
    border-radius:18px; padding:1.6rem 1.9rem; margin-bottom:1.6rem;
}}
.pubv-hero h1 {{ color:#fff; font-size:1.7rem; font-weight:850; margin:0; letter-spacing:-.02em; }}
.pubv-hero .meta {{ color:#9ec0dc; font-size:.9rem; margin-top:.4rem; }}

.pubv-divh {{
    color:#7fffc0; font-size:.75rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase;
    margin:1.6rem 0 .6rem; padding-bottom:.4rem; border-bottom:1px solid rgba(255,255,255,.08);
}}
.pubv-champ {{
    background:linear-gradient(135deg,#1a0533,#6a1b9a); border:2px solid #ffd700; border-radius:14px;
    padding:.9rem 1.2rem; margin:.6rem 0 1rem; display:flex; align-items:center; gap:.8rem;
}}
.pubv-champ .c1 {{ color:#ffd700; font-size:.7rem; font-weight:800; letter-spacing:.1em; }}
.pubv-champ .c2 {{ color:#fff; font-size:1.15rem; font-weight:900; }}

.pubv-round {{ color:#9ec0dc; font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; margin:.9rem 0 .3rem; }}
.pubv-match {{
    background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.07); border-radius:10px;
    padding:.6rem .9rem; margin-bottom:.4rem; display:flex; align-items:center; justify-content:space-between; gap:.8rem;
}}
.pubv-match .pair {{ color:#cfe2f2; font-size:.92rem; flex:1; }}
.pubv-match .pair.win {{ color:#7fffc0; font-weight:700; }}
.pubv-match .sc {{ color:#9ec0dc; font-size:.85rem; font-weight:700; white-space:nowrap; }}
.pubv-match .vs {{ color:#4a7aa0; font-size:.78rem; padding:0 .4rem; }}
.pubv-when {{ color:#5a82a4; font-size:.72rem; white-space:nowrap; }}

.pubv-foot {{ text-align:center; color:#3d6a90; font-size:.78rem; margin:2.5rem 0 1rem; }}
.pubv-foot a {{ color:#7fffc0; text-decoration:none; }}
</style>
"""


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
    st.markdown(
        f'<div class="pubv-brand"><div class="pubv-logo">{BRAND_MONOGRAM}</div>'
        f'<div><b>{escape(BRAND_NAME)}</b><span>Resultados en directo</span></div></div>',
        unsafe_allow_html=True,
    )

    if not is_db_configured():
        st.error("Servicio no disponible.")
        st.stop()

    try:
        row = get_db().get_tournament_public(tournament_id)
    except Exception:
        row = None

    if not row:
        st.markdown(
            '<div class="pubv-hero"><h1>Torneo no encontrado</h1>'
            '<div class="meta">El enlace no es válido o el torneo ya no está disponible.</div></div>',
            unsafe_allow_html=True,
        )
        st.stop()

    try:
        t = tournament_from_db(row)
    except Exception:
        st.error("No se pudo cargar el torneo.")
        st.stop()

    # Cabecera
    _dates = t.start_date.strftime("%d/%m/%Y")
    if t.end_date and t.end_date != t.start_date:
        _dates += f" – {t.end_date.strftime('%d/%m/%Y')}"
    _loc = f" · 📍 {escape(t.location)}" if getattr(t, "location", "") else ""
    st.markdown(
        f'<div class="pubv-hero"><h1>🏆 {escape(t.name)}</h1>'
        f'<div class="meta">📅 {_dates}{_loc}</div></div>',
        unsafe_allow_html=True,
    )

    # Divisiones presentes (multi-categoría) o torneo único
    div_keys = sorted({m.division for m in t.matches if m.division is not None})
    champs = champions_by_division(t)

    def _render_division(div_key, label):
        if label:
            st.markdown(f'<div class="pubv-divh">{escape(label)}</div>', unsafe_allow_html=True)
        champ = champs.get(div_key or "_")
        if champ:
            st.markdown(
                f'<div class="pubv-champ"><span style="font-size:1.4rem">🏆</span>'
                f'<div><div class="c1">CAMPEÓN</div><div class="c2">{escape(champ)}</div></div></div>',
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
            st.markdown(f'<div class="pubv-round">{escape(rnd.display)}</div>', unsafe_allow_html=True)
            for m in sorted(visible, key=lambda x: x.match_number):
                p1cls = "pair win" if (m.winner_id and m.pair_1 and m.winner_id == m.pair_1.id) else "pair"
                p2cls = "pair win" if (m.winner_id and m.pair_2 and m.winner_id == m.pair_2.id) else "pair"
                p1 = escape(m.p1_display); p2 = escape(m.p2_display)
                sc = escape(m.score) if m.score else ("✓" if m.winner_id else "")
                when = _fmt_when(m)
                when_html = f'<span class="pubv-when">{escape(when)}</span>' if when else ""
                st.markdown(
                    f'<div class="pubv-match">'
                    f'<span class="{p1cls}">{p1}</span>'
                    f'<span class="vs">vs</span>'
                    f'<span class="{p2cls}" style="text-align:right">{p2}</span>'
                    f'<span class="sc">{sc}</span>{when_html}</div>',
                    unsafe_allow_html=True,
                )

    if div_keys:
        # Etiquetas legibles de cada división
        from .tournament_models import TournamentCategory, TournamentSubcategory
        def _label(k):
            cat, _, sub = k.partition(":")
            c = next((x for x in TournamentCategory if x.value == cat), None)
            s = next((x for x in TournamentSubcategory if x.value == sub), None)
            return " ".join([p for p in [c.label if c else "", s.label if s else ""] if p]) or k
        for dk in div_keys:
            _render_division(dk, _label(dk))
    else:
        _render_division(None, "")

    st.markdown(
        f'<div class="pubv-foot">Generado con <a href="https://{BRAND_NAME.lower()}.streamlit.app">{escape(BRAND_NAME)}</a>'
        f' · Gestión de torneos y rankings deportivos</div>',
        unsafe_allow_html=True,
    )
    st.stop()
