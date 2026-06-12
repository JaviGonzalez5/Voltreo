"""
Portal público del JUGADOR — ?portal=1 (sin relación con el panel de admins).

Estilo «mistorneosonline»: cualquiera puede ver los torneos y rankings ACTIVOS
de todos los clubs de la plataforma. Además, un jugador puede registrarse
(nombre, apellido, teléfono, email, DNI, club) e iniciar sesión para ver su
perfil: sus dos ELOs y el histórico de partidos (ranking y torneos separados).

La sesión del jugador vive en st.session_state (no toca cookies de admin).
"""

from html import escape

import streamlit as st

from .branding import BRAND_NAME, BRAND_MONOGRAM, BRAND_GRADIENT
from .db import get_db, is_db_configured

_CSS = f"""
<style>
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ display: none !important; }}
.stApp {{ background: #0a1622 !important; }}
.main .block-container {{ max-width: 920px !important; padding: 1.5rem 1.2rem 3rem !important; }}

.ptl-brand {{ display:flex; align-items:center; justify-content:space-between;
  gap:.7rem; margin-bottom:1.2rem; flex-wrap:wrap; }}
.ptl-logo-wrap {{ display:flex; align-items:center; gap:.65rem; }}
.ptl-logo {{ width:38px; height:38px; border-radius:11px; background:{BRAND_GRADIENT};
  display:flex; align-items:center; justify-content:center; color:#fff;
  font-weight:900; font-size:1.2rem; box-shadow:0 4px 16px rgba(0,200,83,.35); }}
.ptl-brand b {{ color:#eaf6ff; font-size:1.05rem; }}
.ptl-brand span.sub {{ color:#4a7aa0; font-size:.68rem; letter-spacing:.14em;
  text-transform:uppercase; display:block; }}

.ptl-hero {{ background:linear-gradient(135deg,#07121f,#0d2b37);
  border:1px solid rgba(127,255,192,.15); border-radius:18px;
  padding:1.5rem 1.8rem; margin-bottom:1.5rem; }}
.ptl-hero h1 {{ color:#fff; font-size:1.55rem; font-weight:850; margin:0; }}
.ptl-hero p {{ color:#9ec0dc; font-size:.92rem; margin:.4rem 0 0; }}

.ptl-sec {{ color:#7fffc0; font-size:.72rem; font-weight:800; letter-spacing:.13em;
  text-transform:uppercase; margin:1.6rem 0 .7rem; padding-bottom:.4rem;
  border-bottom:1px solid rgba(255,255,255,.08); }}

.ptl-card {{ background:#0f2231; border:1px solid #1d3a52; border-radius:14px;
  padding:1rem 1.2rem; margin-bottom:.6rem; }}
.ptl-card-top {{ display:flex; justify-content:space-between; gap:.6rem;
  align-items:baseline; flex-wrap:wrap; }}
.ptl-card-name {{ color:#fff; font-weight:800; font-size:1.02rem; }}
.ptl-club {{ color:#7fffc0; font-size:.74rem; font-weight:700;
  text-transform:uppercase; letter-spacing:.07em; }}
.ptl-meta {{ color:#9ec0dc; font-size:.8rem; margin-top:.25rem; }}
.ptl-pill {{ font-size:.64rem; font-weight:800; letter-spacing:.08em;
  text-transform:uppercase; padding:.2rem .55rem; border-radius:20px;
  background:rgba(0,200,83,.16); color:#7fffc0;
  border:1px solid rgba(127,255,192,.4); white-space:nowrap; }}
.ptl-links {{ margin-top:.55rem; display:flex; gap:.9rem; flex-wrap:wrap; }}
.ptl-links a {{ color:#7fffc0; font-size:.82rem; font-weight:700; text-decoration:none; }}
.ptl-links a:hover {{ text-decoration:underline; }}
.ptl-empty {{ color:#6b8bab; font-size:.85rem; font-style:italic; padding:.6rem 0; }}
.ptl-foot {{ text-align:center; color:#3d6a90; font-size:.76rem; margin-top:2.4rem; }}
.ptl-foot a {{ color:#7fffc0; text-decoration:none; }}
</style>
"""


def _topbar(logged_name: str = "") -> None:
    right = (f'<span style="color:#9ec0dc;font-size:.85rem">👋 {escape(logged_name)}</span>'
             if logged_name else "")
    st.markdown(
        f'<div class="ptl-brand"><div class="ptl-logo-wrap">'
        f'<div class="ptl-logo">{BRAND_MONOGRAM}</div>'
        f'<div><b>{escape(BRAND_NAME)}</b>'
        f'<span class="sub">Portal del jugador</span></div></div>{right}</div>',
        unsafe_allow_html=True,
    )


def _fmt_range(s: str, e: str) -> str:
    def _f(x):
        p = str(x).split("-")
        return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(x)
    return f"{_f(s)} → {_f(e)}" if e and e != s else _f(s)


def _base_url() -> str:
    from .branding import public_base_url
    return public_base_url()


def _render_directory() -> None:
    """Torneos y rankings activos de TODOS los clubs (visible sin login)."""
    from .db_players import list_active_tournaments_all, list_active_phases_all

    st.markdown('<div class="ptl-sec">🏆 Torneos activos</div>', unsafe_allow_html=True)
    try:
        tournaments = list_active_tournaments_all()
    except Exception:
        tournaments = []
        st.warning("No se pudieron cargar los torneos. Inténtalo más tarde.")
    if not tournaments:
        st.markdown('<div class="ptl-empty">Ahora mismo no hay torneos activos.</div>',
                    unsafe_allow_html=True)
    for t in tournaments:
        pill = '<span class="ptl-pill">📩 Inscripción abierta</span>' \
            if t["registration_open"] else ""
        loc = f' · 📍 {escape(t["location"])}' if t.get("location") else ""
        links = (f'<a href="{_base_url()}/?t={t["id"]}" target="_blank">📊 Resultados</a>'
                 + (f'<a href="{_base_url()}/?join={t["id"]}" target="_blank">📝 Inscribirse</a>'
                    if t["registration_open"] else ""))
        st.markdown(
            f'<div class="ptl-card"><div class="ptl-card-top">'
            f'<div><div class="ptl-club">{escape(t["club_name"])}</div>'
            f'<div class="ptl-card-name">🏆 {escape(t["name"])}</div></div>{pill}</div>'
            f'<div class="ptl-meta">📅 {_fmt_range(t["start_date"], t["end_date"])}{loc}</div>'
            f'<div class="ptl-links">{links}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="ptl-sec">📊 Rankings activos</div>', unsafe_allow_html=True)
    try:
        phases = list_active_phases_all()
    except Exception:
        phases = []
    if not phases:
        st.markdown('<div class="ptl-empty">Ahora mismo no hay rankings activos.</div>',
                    unsafe_allow_html=True)
    for p in phases:
        st.markdown(
            f'<div class="ptl-card"><div class="ptl-card-top">'
            f'<div><div class="ptl-club">{escape(p["club_name"])}</div>'
            f'<div class="ptl-card-name">📊 {escape(p["name"])}</div></div></div>'
            f'<div class="ptl-meta">📅 {_fmt_range(p["start_date"], p["end_date"])}</div>'
            f'<div class="ptl-links">'
            f'<a href="{_base_url()}/?r={p["id"]}" target="_blank">🏅 Ver clasificación</a>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


def _render_profile(account: dict) -> None:
    """Perfil del jugador logueado: 2 ELOs + históricos separados."""
    from .db_players import relink_player_identity
    from .db_elo import get_player_by_id, get_player_history

    player = None
    if account.get("player_id"):
        try:
            player = get_player_by_id(account["player_id"])
        except Exception:
            player = None
    if player is None:
        player = relink_player_identity(account)
    if player is None:
        st.info("Tu perfil aún no tiene partidos vinculados. Cuando tu club "
                "registre un resultado con tu nombre, aparecerá aquí.")
        return

    def _wr(pj, g):
        return round(g * 100 / pj) if pj else 0
    pr = player.get("matches_played_ranking", 0)
    pt = player.get("matches_played_tournament", 0)
    st.markdown(
        f'<div class="ptl-hero"><h1>👤 {escape(player["full_name"])}</h1>'
        f'<p>📊 ELO Ranking: <b style="color:#ffd700">{player.get("elo_ranking", 1200)}</b>'
        f' ({pr} PJ · {_wr(pr, player.get("matches_won_ranking", 0))}% vict.) &nbsp;·&nbsp; '
        f'🏆 ELO Torneos: <b style="color:#ffd700">{player.get("elo_tournament", 1200)}</b>'
        f' ({pt} PJ · {_wr(pt, player.get("matches_won_tournament", 0))}% vict.)</p></div>',
        unsafe_allow_html=True,
    )

    tab_r, tab_t = st.tabs(["📊 Mis partidos de ranking", "🏆 Mis partidos de torneos"])
    for tab, ctx in ((tab_r, "ranking"), (tab_t, "tournament")):
        with tab:
            try:
                hist = get_player_history(player["id"], ctx, limit=50)
            except Exception:
                hist = []
            if not hist:
                st.markdown('<div class="ptl-empty">Sin partidos todavía en este '
                            'contexto.</div>', unsafe_allow_html=True)
                continue
            import pandas as pd
            rows = [{
                "Fecha": (h.get("played_at") or "")[:10],
                "Evento": h.get("tournament_name") or "—",
                "Resultado": (h.get("result") or "").replace("won", "🏆 Ganó")
                                                    .replace("lost", "❌ Perdió"),
                "Rival": h.get("opponent_names", ""),
                "Δ ELO": (f'+{h["delta"]}' if h.get("delta", 0) > 0 else str(h.get("delta", 0))),
                "ELO": h.get("elo_after"),
            } for h in hist]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_player_portal() -> None:
    """Página completa del portal. Llama a st.stop()."""
    st.markdown(_CSS, unsafe_allow_html=True)

    if not is_db_configured():
        st.error("Servicio no disponible.")
        st.stop()

    account = st.session_state.get("_portal_account")
    _topbar(account.get("name", "") if account else "")

    if account:
        # ── Vista logueada ────────────────────────────────────────────────────
        c1, c2 = st.columns([4, 1])
        with c2:
            if st.button("Cerrar sesión", key="ptl_logout", use_container_width=True):
                st.session_state.pop("_portal_account", None)
                st.rerun()
        tab_dir, tab_me = st.tabs(["🗓️ Competiciones", "👤 Mi perfil"])
        with tab_dir:
            _render_directory()
        with tab_me:
            _render_profile(account)
    else:
        # ── Vista pública ─────────────────────────────────────────────────────
        st.markdown(
            f'<div class="ptl-hero"><h1>Torneos y rankings de pádel y pickleball</h1>'
            f'<p>Consulta las competiciones activas de todos los clubs, inscríbete a '
            f'torneos y sigue tu ELO y tu histórico de partidos.</p></div>',
            unsafe_allow_html=True,
        )
        tab_dir, tab_login, tab_signup = st.tabs(
            ["🗓️ Competiciones", "🔑 Entrar", "✨ Crear mi perfil"])

        with tab_dir:
            _render_directory()

        with tab_login:
            with st.form("ptl_login"):
                em = st.text_input("Email")
                pw = st.text_input("Contraseña", type="password")
                ok = st.form_submit_button("Entrar", type="primary",
                                           use_container_width=True)
            if ok:
                from .db_players import login_player
                try:
                    acc = login_player(em, pw)
                except Exception:
                    acc = None
                    st.error("No se pudo comprobar el acceso. Inténtalo más tarde.")
                if acc:
                    acc.pop("password_hash", None)
                    st.session_state["_portal_account"] = acc
                    st.rerun()
                elif acc is None:
                    st.error("Email o contraseña incorrectos.")

        with tab_signup:
            try:
                clubs = get_db().list_clubs()
            except Exception:
                clubs = []
            if not clubs:
                st.info("Todavía no hay clubs disponibles.")
            else:
                club_opts = {c["name"]: c["id"] for c in clubs}
                with st.form("ptl_signup"):
                    club_sel = st.selectbox("Tu club", list(club_opts))
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        name = st.text_input("Nombre *")
                        phone = st.text_input("Teléfono *")
                        dni = st.text_input("DNI / NIE *",
                                            help="Solo para identificación del club. No se muestra públicamente.")
                    with cc2:
                        surname = st.text_input("Primer apellido *")
                        email = st.text_input("Email *")
                    pw1 = st.text_input("Contraseña *", type="password")
                    pw2 = st.text_input("Repite la contraseña *", type="password")
                    sub = st.form_submit_button("Crear mi perfil", type="primary",
                                                use_container_width=True)
                if sub:
                    from .db_players import validate_signup, create_player_account
                    errs = validate_signup(name, surname, phone, email, dni, pw1, pw2)
                    for e in errs:
                        st.error(e)
                    if not errs:
                        try:
                            acc = create_player_account(
                                club_opts[club_sel], name, surname, phone,
                                email, dni, pw1,
                            )
                            acc.pop("password_hash", None)
                            st.session_state["_portal_account"] = acc
                            st.success("✅ Perfil creado. ¡Bienvenido!")
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))
                        except Exception:
                            st.error("No se pudo crear el perfil. Inténtalo más tarde.")

    st.markdown(
        f'<div class="ptl-foot">Impulsado por <a href="{_base_url()}">'
        f'{escape(BRAND_NAME)}</a> · Gestión de torneos y rankings</div>',
        unsafe_allow_html=True,
    )
    st.stop()
