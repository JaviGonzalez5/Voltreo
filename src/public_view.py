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

/* ── Móvil ── */
@media (max-width: 640px) {{
    .main .block-container {{
        padding-top: 1rem !important;
        padding-left: .8rem !important;
        padding-right: .8rem !important;
    }}
    .pubv-hero {{ padding: 1.1rem 1.1rem !important; border-radius: 12px !important; }}
    .pubv-hero h1 {{ font-size: 1.35rem !important; }}
    .pubv-hero .meta {{ font-size: .82rem !important; }}
    .pubv-divh {{ font-size: .68rem !important; }}
    .pubv-match {{ flex-wrap: wrap; gap: .4rem !important; }}
    /* Inputs grandes para dedos */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stTextArea"] textarea {{
        font-size: 16px !important;
        min-height: 44px !important;
    }}
    .stButton > button {{ min-height: 48px !important; font-size: .95rem !important; }}
    .stForm [data-testid="stVerticalBlock"] > div {{ gap: .5rem !important; }}
}}

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


def render_public_registration(tournament_id: str) -> None:
    """
    Página pública de inscripción en un torneo.
    Accesible vía ?join=<tournament_id> sin login.
    El jugador rellena sus datos y queda como inscripción PENDIENTE
    hasta que el admin la apruebe.
    """
    from datetime import datetime as _dtt
    from .tournament_models import TournamentRegistration, RegistrationStatus

    st.markdown(_PUBLIC_CSS, unsafe_allow_html=True)

    # Cabecera de marca
    st.markdown(
        f'<div class="pubv-brand"><div class="pubv-logo">{BRAND_MONOGRAM}</div>'
        f'<div><b>{escape(BRAND_NAME)}</b><span>Inscripción en torneo</span></div></div>',
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
        from .db_converters import tournament_from_db as _tfdb
        t = _tfdb(row)
    except Exception:
        st.error("No se pudo cargar el torneo.")
        st.stop()

    # Info del torneo
    _dates = t.start_date.strftime("%d/%m/%Y")
    if t.end_date and t.end_date != t.start_date:
        _dates += f" – {t.end_date.strftime('%d/%m/%Y')}"
    _loc = f" · 📍 {escape(t.location)}" if getattr(t, "location", "") else ""

    st.markdown(
        f'<div class="pubv-hero">'
        f'<h1>🎾 {escape(t.name)}</h1>'
        f'<div class="meta">📅 {_dates}{_loc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Comprobar si las inscripciones están abiertas
    if not t.is_registration_active():
        st.markdown(
            '<div style="text-align:center;padding:3rem 1.5rem;background:#f5f8fc;'
            'border-radius:16px;border:2px dashed #d0e0f0;margin:1rem 0">'
            '<div style="font-size:2.5rem;margin-bottom:.6rem">🔒</div>'
            '<div style="font-size:1.1rem;font-weight:700;color:#1b3a58;margin-bottom:.4rem">'
            'Las inscripciones están cerradas</div>'
            '<div style="font-size:.9rem;color:#7f9ab5">'
            'El club aún no ha abierto el registro para este torneo. '
            'Contacta con los organizadores.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    # Mostrar categorías disponibles
    _div_keys = list(getattr(t, "divisions", []) or [])
    _, _div_labels = None, {}
    try:
        from .tournament_models import TournamentCategory, TournamentSubcategory
        for cat_v, _, sub_v in [k.partition(":") for k in _div_keys]:
            c = next((x for x in TournamentCategory if x.value == cat_v), None)
            s = next((x for x in TournamentSubcategory if x.value == sub_v), None)
            _div_labels[f"{cat_v}:{sub_v}"] = " ".join([p for p in [c.label if c else "", s.label if s else ""] if p]) or f"{cat_v}:{sub_v}"
    except Exception:
        pass

    # Contadores por división para mostrar plazas
    _max_pairs = getattr(t, "registration_max_pairs", {}) or {}
    _confirmed_total = t.confirmed_count()
    _pending_total   = len([r for r in getattr(t, "registrations", [])
                             if r.status == RegistrationStatus.PENDING])

    # Resumen de plazas
    _slots_parts = []
    if _div_keys:
        for _dk in _div_keys:
            _mx = _max_pairs.get(_dk, 0)
            _cn = t.confirmed_count(_dk)
            _lbl = _div_labels.get(_dk, _dk)
            if _mx:
                _slots_parts.append(f"{_lbl}: {_cn}/{_mx}")
            else:
                _slots_parts.append(f"{_lbl}: {_cn} inscritas")
    _slots_str = " · ".join(_slots_parts) if _slots_parts else f"{_confirmed_total} parejas confirmadas"

    st.markdown(
        f'<div style="background:rgba(0,200,83,.07);border:1px solid rgba(0,200,83,.25);'
        f'border-radius:12px;padding:.9rem 1.2rem;margin:1rem 0;font-size:.9rem;color:#005a29;font-weight:600">'
        f'✅ Inscripciones abiertas · {_slots_str}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Guardar "inscrito con éxito" en session_state para no mostrar el form de nuevo
    if st.session_state.get(f"_reg_done_{tournament_id}"):
        st.success("✅ ¡Inscripción enviada! El club revisará tu solicitud y te confirmará.")
        st.caption("Puedes cerrar esta ventana o compartir el enlace con otro jugador.")
        st.stop()

    st.markdown(
        '<div style="font-size:.7rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:#00843d;margin:1.4rem 0 .5rem">FORMULARIO DE INSCRIPCIÓN</div>',
        unsafe_allow_html=True,
    )

    with st.form("public_registration_form"):
        st.markdown("**Datos de la pareja**")
        pair_name = st.text_input("Nombre de la pareja (ej. García / López)", placeholder="García / López")

        if _div_keys:
            # Construir opciones filtrando categorías llenas
            def _div_opt_label(k):
                mx = _max_pairs.get(k, 0)
                cn = t.confirmed_count(k)
                lbl = _div_labels.get(k, k)
                if mx and cn >= mx:
                    return f"{lbl} — COMPLETO ({cn}/{mx})"
                if mx:
                    return f"{lbl} ({cn}/{mx} plazas)"
                return lbl

            div_opts  = ["— Elige tu categoría —"] + [_div_opt_label(k) for k in _div_keys]
            div_sel_display = st.selectbox("Categoría", options=div_opts)
            # Recuperar la clave original a partir del display seleccionado
            div_sel_key = None
            for k in _div_keys:
                if _div_opt_label(k) == div_sel_display:
                    div_sel_key = k
                    break
        else:
            div_sel_key = None

        st.divider()
        # Jugador 1 — columnas que colapsan a una en móvil
        st.markdown("**Jugador 1**")
        p1_name  = st.text_input("Nombre del jugador 1", key="p1n", placeholder="Carlos García")
        _p1col1, _p1col2 = st.columns(2)
        with _p1col1: p1_phone = st.text_input("Teléfono J1", key="p1ph", placeholder="+34 600 000 000")
        with _p1col2: p1_email = st.text_input("Email J1 (opcional)", key="p1em", placeholder="carlos@email.com")

        st.markdown("**Jugador 2**")
        p2_name  = st.text_input("Nombre del jugador 2", key="p2n", placeholder="Marta López")
        _p2col1, _p2col2 = st.columns(2)
        with _p2col1: p2_phone = st.text_input("Teléfono J2", key="p2ph", placeholder="+34 600 000 001")
        with _p2col2: p2_email = st.text_input("Email J2 (opcional)", key="p2em", placeholder="marta@email.com")

        notes = st.text_area("Nota para el organizador (opcional)", placeholder="Cualquier información adicional…", height=70)

        # ── Disponibilidad por días (solo si el admin lo ha activado) ──────
        _ask_avail = getattr(t, "registration_ask_availability", False)
        unavailable_selected: list[str] = []
        availability_windows: dict = {}
        if _ask_avail:
            from datetime import timedelta as _td
            _days_range = []
            _d = t.start_date
            while _d <= t.end_date:
                _days_range.append(_d)
                _d = _d + _td(days=1)

            if _days_range:
                st.markdown("**📅 ¿Cuándo puedes jugar?**")
                st.caption("Indica tu disponibilidad. Si puedes todo el día, deja los valores por defecto.")

                # Días únicos de la semana presentes en el torneo (en orden de aparición)
                _seen_wdays: list[int] = []
                for _dd in _days_range:
                    if _dd.weekday() not in _seen_wdays:
                        _seen_wdays.append(_dd.weekday())

                # Opciones de hora cada 30 min: 07:00 → 23:30
                _time_opts = [f"{h:02d}:{m:02d}" for h in range(7, 24) for m in (0, 30)]
                _idx_9  = _time_opts.index("09:00") if "09:00" in _time_opts else 0
                _idx_22 = _time_opts.index("22:00") if "22:00" in _time_opts else len(_time_opts) - 1

                _day_names_full = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                _estado_opts = {_dname: [] for _dname in _day_names_full}

                for _wday in _seen_wdays:
                    _wkey = str(_wday)
                    _dname = _day_names_full[_wday]

                    # Cabecera del día usando subheader nativo de Streamlit
                    # (siempre visible en modo claro y oscuro, en móvil y escritorio)
                    st.subheader(f"📅 {_dname}", divider="green")

                    _can_play = st.selectbox(
                        f"¿Puedes jugar el {_dname}?",
                        ["✅ Puedo", "❌ No puedo"],
                        key=f"avail_st_{_wkey}",
                    )

                    if _can_play == "❌ No puedo":
                        for _dd2 in _days_range:
                            if _dd2.weekday() == _wday:
                                unavailable_selected.append(_dd2.isoformat())
                    else:
                        _fc1, _fc2 = st.columns(2)
                        with _fc1:
                            _from = st.selectbox(
                                "⏩ Desde", _time_opts, index=_idx_9,
                                key=f"avail_from_{_wkey}",
                            )
                        with _fc2:
                            _to = st.selectbox(
                                "⏹ Hasta", _time_opts, index=_idx_22,
                                key=f"avail_to_{_wkey}",
                            )
                        if _from != "07:00" or _to != "23:30":
                            for _dd2 in _days_range:
                                if _dd2.weekday() == _wday:
                                    availability_windows[_dd2.isoformat()] = {"from": _from, "to": _to}

        submitted = st.form_submit_button("📩 Enviar inscripción", type="primary", use_container_width=True)

    if submitted:
        errors = []
        if not pair_name.strip():
            errors.append("Rellena el nombre de la pareja.")
        if not p1_name.strip():
            errors.append("Rellena el nombre del Jugador 1.")
        if not p2_name.strip():
            errors.append("Rellena el nombre del Jugador 2.")
        if _div_keys and not div_sel_key:
            errors.append("Selecciona una categoría.")
        # Bloquear si la categoría elegida ya está llena
        if div_sel_key and t.is_division_full(div_sel_key):
            errors.append(f"La categoría seleccionada ya está completa. Elige otra o contacta con el organizador.")
        for e in errors:
            st.error(e)
        if not errors:
            reg = TournamentRegistration(
                pair_name   = pair_name.strip(),
                player1_name  = p1_name.strip(),
                player1_phone = p1_phone.strip() or None,
                player1_email = p1_email.strip() or None,
                player2_name  = p2_name.strip(),
                player2_phone = p2_phone.strip() or None,
                player2_email = p2_email.strip() or None,
                division      = div_sel_key,
                notes         = notes.strip(),
                unavailable_dates     = unavailable_selected,
                availability_windows  = availability_windows,
                status        = RegistrationStatus.PENDING,
                submitted_at  = _dtt.utcnow().isoformat(),
            )
            # Guardar en BD
            try:
                t.registrations.append(reg)
                from .db_converters import tournament_to_db as _ttdb
                payload = _ttdb(t, row.get("club_id", ""), t.id)
                get_db().upsert_tournament(
                    club_id=row.get("club_id", ""),
                    name=payload["name"],
                    start_date=payload["start_date"],
                    end_date=payload["end_date"],
                    tournament_data=payload["tournament_data"],
                    tournament_id=t.id,
                )
                st.session_state[f"_reg_done_{tournament_id}"] = True
                st.rerun()
            except Exception as _e:
                st.error(f"Error al guardar la inscripción: {_e}")

    st.markdown(
        f'<div class="pubv-foot">Organizado con <a href="https://{BRAND_NAME.lower()}.streamlit.app">'
        f'{escape(BRAND_NAME)}</a></div>',
        unsafe_allow_html=True,
    )
    st.stop()
