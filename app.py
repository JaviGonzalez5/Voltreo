"""
Ranking Padel Automator — Interfaz Streamlit
"""
from __future__ import annotations

import re
import sys
import io
from pathlib import Path
from datetime import date, time, datetime, timedelta

import pandas as pd
import streamlit as st

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
    validate_groups_df, validate_bookings_df, validate_phase_dates, validate_groups
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
.ppcal{border-collapse:collapse;width:100%;font-family:sans-serif;font-size:12px}
.ppcal th{background:#1e3a5f;color:#fff;padding:8px 4px;text-align:center;border:1px solid #b0b8c4;white-space:nowrap}
.ppcal td{padding:3px;border:1px solid #dde3ea;vertical-align:top;background:#fafbfc;min-width:110px}
.ppcal .time-col{background:#e9eef5;font-weight:600;text-align:center;color:#2c3e50;font-size:13px;padding:6px 8px;white-space:nowrap;width:52px}
.ppcal .has-match{background:#fff}
.pp-card{border-radius:5px;padding:5px 7px;margin:2px 0;border-left:4px solid #1976d2;background:#e8f4fd;line-height:1.35}
.pp-card.conflict{background:#fde8e8;border-left-color:#d32f2f}
.pp-vs{font-weight:700;font-size:11px;color:#1a237e}
.pp-info{font-size:10px;color:#546e7a;margin-top:1px}
.pp-court{font-size:10px;font-weight:600;color:#37474f}
.day-name{font-size:13px;font-weight:700}
.day-date{font-size:11px;opacity:.85;margin-top:1px}
.today-hdr{background:#2e7d32 !important}
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
                    is_conf = m.status.value == "conflict"
                    card_cls = "pp-card conflict" if is_conf else "pp-card"
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
            id=str(__import__("uuid").uuid4()),
            name=str(row["player1_name"]).strip(),
            surname="",
            email=str(row.get("player1_email", "")).strip() or None,
            phone=str(row.get("player1_phone", "")).strip() or None,
        )
        p2 = Player.model_construct(
            id=str(__import__("uuid").uuid4()),
            name=str(row["player2_name"]).strip(),
            surname="",
            email=str(row.get("player2_email", "")).strip() or None,
            phone=str(row.get("player2_phone", "")).strip() or None,
        )
        pair = Pair.model_construct(
            id=str(__import__("uuid").uuid4()),
            name=str(row["pair_name"]).strip(),
            player_1=p1,
            player_2=p2,
            group_id=gid,
            available_weekdays=[],
            available_from=None,
            available_until=None,
            availability_notes="",
            preferred_weekday=None,
            preferred_time=None,
        )
        groups_dict[gid].pairs.append(pair)
    return list(groups_dict.values())


def _df_to_bookings(df: pd.DataFrame) -> list[Booking]:
    """Convierte un DataFrame de reservas al modelo Booking."""
    bookings = []
    for _, row in df.iterrows():
        bookings.append(Booking.model_construct(
            id=str(__import__("uuid").uuid4()),
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
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# ---------------------------------------------------------------------------
# Sidebar — navegación
# ---------------------------------------------------------------------------

st.sidebar.title("🎾 Ranking Pádel")
st.sidebar.markdown("---")

PAGES = {
    "⚙️ Configuración": "config",
    "📥 Importar datos": "import",
    "📅 Generar calendario": "generate",
    "📤 Exportar": "export",
    "🔍 Revisión": "review",
    "🔗 Publicar en Syltek": "syltek",
}
page_label = st.sidebar.radio("Navegación", list(PAGES.keys()))
page = PAGES[page_label]

dry_run_color = "🟢" if st.session_state.dry_run else "🔴"
st.sidebar.markdown(f"**Modo:** {dry_run_color} {'DRY-RUN (sin escritura)' if st.session_state.dry_run else 'ESCRITURA REAL'}")
st.sidebar.markdown("---")

# Indicadores de estado
st.sidebar.markdown("**Estado del flujo:**")
st.sidebar.markdown(f"{'✅' if st.session_state.data_loaded else '⬜'} Datos cargados")
st.sidebar.markdown(f"{'✅' if st.session_state.matches_generated else '⬜'} Enfrentamientos generados")
st.sidebar.markdown(f"{'✅' if st.session_state.matches_scheduled else '⬜'} Horarios asignados")

# ---------------------------------------------------------------------------
# PÁGINA 1: Configuración
# ---------------------------------------------------------------------------

if page == "config":
    st.title("⚙️ Configuración")
    st.info("Las credenciales se leen del archivo `.env`. Aquí configuras los parámetros de la fase.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Credenciales Syltek")
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
                    from src.syltek_connector import run_login_check
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
        st.subheader("Parámetros de la fase")
        phase_name = st.text_input("Nombre de la fase", value="Fase 1")
        start_date = st.date_input("Fecha de inicio", value=date.today() + timedelta(days=7))
        end_date = st.date_input("Fecha de fin", value=date.today() + timedelta(days=42))

        col2a, col2b = st.columns(2)
        with col2a:
            start_hour = st.time_input("Hora mínima de juego", value=time(16, 0))
        with col2b:
            end_hour = st.time_input("Hora máxima de juego", value=time(22, 30))

        match_duration = st.slider("Duración del partido (min)", 60, 120, 90, step=30)
        slot_step = st.slider(
            "Cada cuántos minutos probar inicios",
            30, 90, 30, step=30,
            help="30 min da más variedad: 16:00, 16:30, 17:00... En 90 min solo prueba 16:00, 17:30, 19:00, 20:30.",
        )
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
                    slot_step_minutes=slot_step,
                    max_matches_per_week=max_per_week,
                    min_days_between_matches=min_days_between,
                    random_seed=int(random_seed_val) if random_seed_val is not None else None,
                    balance_weights=BalanceWeights.model_construct(
                        same_hour_penalty=10.0,
                        same_weekday_penalty=6.0,
                        same_court_penalty=2.0,
                        day_load_penalty=1.5,
                        court_load_penalty=1.0,
                        global_hour_load_penalty=3.0,
                        group_hour_penalty=14.0,
                        early_day_bonus=0.2,
                        preferred_slot_bonus=1000.0,
                    ),
                )
                st.session_state.phase = phase
                st.session_state.courts = courts
                st.session_state["club_name"] = club_name
                st.success("✅ Configuración guardada.")

# ---------------------------------------------------------------------------
# PÁGINA 2: Importar datos
# ---------------------------------------------------------------------------

elif page == "import":
    st.title("📥 Importar datos")
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
            data=Path("sample_data/groups_example.csv").read_text(encoding="utf-8"),
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
                st.success(f"✅ {len(groups)} grupos cargados con {sum(len(g.pairs) for g in groups)} parejas.")

        if st.session_state.groups:
            st.subheader("Vista previa de grupos")
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
            data=Path("sample_data/bookings_example.csv").read_text(encoding="utf-8"),
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
                    from src.syltek_connector import SyltekConnector
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
                    from src.syltek_connector import SyltekConnector
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
                    from src.syltek_connector import SyltekConnector
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
                        from src.syltek_connector import SyltekConnector
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
                                from src.syltek_connector import _parse_occupied_slots as _pos
                                parsed_bk = _pos(r_diag.text, diag_date)
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
                    from src.syltek_connector import SyltekConnector
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
                            with st.expander("Ver reservas importadas"):
                                rows_imp = [
                                    {
                                        "Pista": b.court_name,
                                        "Fecha": b.start_datetime.strftime("%d/%m/%Y"),
                                        "Inicio": b.start_datetime.strftime("%H:%M"),
                                        "Fin": b.end_datetime.strftime("%H:%M"),
                                        "Descripción": b.description[:50],
                                    }
                                    for b in bookings[:100]
                                ]
                                st.dataframe(pd.DataFrame(rows_imp), use_container_width=True)
                                if len(bookings) > 100:
                                    st.caption(f"Mostrando 100 de {len(bookings)} reservas.")
                        else:
                            st.warning(
                                "No se encontraron reservas existentes en ese rango de fechas. "
                                "Puede ser normal si las fechas son futuras o si el parsing necesita ajuste."
                            )

# ---------------------------------------------------------------------------
# PÁGINA 3: Generar calendario
# ---------------------------------------------------------------------------

elif page == "generate":
    st.title("📅 Generar calendario")

    if not st.session_state.data_loaded or not st.session_state.groups:
        st.warning("Primero debes cargar los datos de grupos en la página **Importar datos**.")
        st.stop()

    if not st.session_state.phase:
        st.warning("Primero debes guardar la configuración de fase en **Configuración**.")
        st.stop()

    phase: RankingPhase = st.session_state.phase

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Acciones")

        if st.button("⚡ Generar enfrentamientos", type="primary"):
            matches = generate_all_matches(phase.groups)
            st.session_state.matches = matches
            st.session_state.matches_generated = True
            st.session_state.matches_scheduled = False
            st.session_state.schedule_result = None
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

                # Ejecutar validación automáticamente
                from src.schedule_validator import validate_schedule, validation_summary
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
                    from src.excel_template_exporter import export_groups_to_template
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
            st.subheader("Resumen")
            result: ScheduleResult = st.session_state.schedule_result
            if result:
                m1, m2, m3 = st.columns(3)
                m1.metric("Programados", result.scheduled_count, delta=None)
                m2.metric("Conflictos", result.conflict_count,
                          delta=f"-{result.conflict_count}" if result.conflict_count else None,
                          delta_color="inverse")
                m3.metric("Tasa de éxito", f"{result.success_rate:.1f}%")

                # ---- Panel rápido de validación ----
                violations = st.session_state.get("schedule_violations")
                if violations is None and st.session_state.matches_scheduled:
                    from src.schedule_validator import validate_schedule, validation_summary
                    violations = validate_schedule(result, phase)
                    st.session_state["schedule_violations"] = violations

                if violations is not None:
                    from src.schedule_validator import validation_summary, SEVERITY_EMOJI
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
        st.subheader("Calendario generado")

        # Filtros globales (aplican a ambas vistas)
        fc1, fc2, fc3 = st.columns(3)
        group_names = list({m.group_name for m in st.session_state.matches})
        sel_group = fc1.multiselect("Filtrar por grupo", group_names, default=group_names)
        status_opts = [s.value for s in MatchStatus]
        sel_status = fc2.multiselect("Estado", status_opts, default=status_opts)
        pair_names = list({m.pair_1.display_name for m in st.session_state.matches} |
                          {m.pair_2.display_name for m in st.session_state.matches})
        sel_pair = fc3.multiselect("Pareja (contiene)", pair_names, default=[])

        filtered = [
            m for m in st.session_state.matches
            if m.group_name in sel_group
            and m.status.value in sel_status
            and (not sel_pair or m.pair_1.display_name in sel_pair or m.pair_2.display_name in sel_pair)
        ]

        # Índice de IDs para poder mapear filas editadas → objetos Match
        filtered_ids = [m.id for m in filtered]
        match_id_to_obj = {m.id: m for m in st.session_state.matches}

        # Construir lookup de pistas disponibles
        court_name_to_obj: dict = {}
        for c in (st.session_state.courts or []):
            court_name_to_obj[c.name] = c
        for m in st.session_state.matches:
            if m.court and m.court.name not in court_name_to_obj:
                court_name_to_obj[m.court.name] = m.court
        court_names = sorted(court_name_to_obj.keys())

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
                    for col, new_val in changes.items():
                        if col == "Fecha" and new_val is not None:
                            from datetime import date as _date
                            if isinstance(new_val, str):
                                from datetime import datetime as _dt
                                match_obj.suggested_date = _dt.fromisoformat(new_val).date()
                            else:
                                match_obj.suggested_date = new_val
                        elif col == "Inicio" and new_val is not None:
                            if isinstance(new_val, str):
                                parts = new_val.split(":")
                                match_obj.suggested_start_time = time(int(parts[0]), int(parts[1]))
                            else:
                                match_obj.suggested_start_time = new_val
                        elif col == "Fin" and new_val is not None:
                            if isinstance(new_val, str):
                                parts = new_val.split(":")
                                match_obj.suggested_end_time = time(int(parts[0]), int(parts[1]))
                            else:
                                match_obj.suggested_end_time = new_val
                        elif col == "Pista" and new_val and new_val in court_name_to_obj:
                            match_obj.court = court_name_to_obj[new_val]
                        elif col == "Estado" and new_val:
                            try:
                                match_obj.status = MatchStatus(new_val)
                                user_set_status = True
                            except ValueError:
                                pass
                        elif col == "Observaciones":
                            match_obj.notes = str(new_val or "")
                            match_obj.conflict_reason = None

                    if not user_set_status:
                        match_obj.status = MatchStatus.MANUALLY_MODIFIED
                    changed += 1

                if changed:
                    st.success(f"✅ {changed} partido(s) guardado(s) correctamente.")
                    del st.session_state["matches_editor"]
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
                    conflicts_week = [m for m in week_ms if m.status.value == "conflict"]
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
    st.title("📤 Exportar")

    if not st.session_state.matches_scheduled:
        st.warning("Primero genera y asigna los horarios en **Generar calendario**.")
        st.stop()

    phase: RankingPhase = st.session_state.phase
    result: ScheduleResult = st.session_state.schedule_result
    club_name = st.session_state.get("club_name", "El Club")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Excel del calendario")

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
                from src.excel_template_exporter import export_groups_to_template
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
        st.subheader("✉️ Mensajes para jugadores")
        msg_type = st.radio("Tipo de mensaje", ["Por grupo", "Por pareja"])
        if st.button("Generar mensajes"):
            matches = st.session_state.matches
            if msg_type == "Por grupo":
                msgs = generate_all_group_messages(phase.groups, matches, club_name)
                for gid, txt in msgs.items():
                    group = next((g for g in phase.groups if g.id == gid), None)
                    label = group.name if group else gid
                    with st.expander(f"Mensaje — {label}"):
                        st.text_area("", txt, height=300, key=f"msg_g_{gid}")
                        st.download_button(
                            "⬇️ Descargar .txt",
                            data=txt,
                            file_name=f"mensaje_{label}.txt",
                            key=f"dl_g_{gid}",
                        )
            else:
                msgs = generate_all_pair_messages(phase.groups, matches, club_name)
                for pid, txt in msgs.items():
                    pair = next(
                        (p for g in phase.groups for p in g.pairs if p.id == pid), None
                    )
                    label = pair.display_name if pair else pid
                    with st.expander(f"Mensaje — {label}"):
                        st.text_area("", txt, height=300, key=f"msg_p_{pid}")

# ---------------------------------------------------------------------------
# PÁGINA 5: Revisión
# ---------------------------------------------------------------------------

elif page == "review":
    st.title("🔍 Revisión y diagnóstico")

    if not st.session_state.schedule_result:
        st.info("No hay resultado de planificación aún. Genera y asigna horarios primero.")
        st.stop()

    result: ScheduleResult = st.session_state.schedule_result
    phase: RankingPhase = st.session_state.phase

    # Métricas globales
    st.subheader("Resumen general")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total partidos", result.total_matches)
    m2.metric("Programados", result.scheduled_count)
    m3.metric("Conflictos", result.conflict_count)
    m4.metric("Éxito", f"{result.success_rate:.1f}%")

    # ---- Validación post-asignación ----
    st.subheader("🔎 Validación del calendario")
    from src.schedule_validator import validate_schedule, validation_summary, SEVERITY_EMOJI

    if st.button("🔄 Ejecutar validación completa", type="primary"):
        violations = validate_schedule(result, phase)
        st.session_state["schedule_violations"] = violations

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
        st.subheader("⚠️ Partidos con conflicto")
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
        st.subheader("📆 Partidos por día")
        from collections import Counter
        day_count = Counter(
            m.suggested_date.strftime("%A %d/%m") for m in result.scheduled if m.suggested_date
        )
        df_days = pd.DataFrame(
            {"Día": list(day_count.keys()), "Partidos": list(day_count.values())}
        ).sort_values("Día")
        st.bar_chart(df_days.set_index("Día"))

        # Balanceo: franja horaria y día de la semana
        st.subheader("⚖️ Balanceo del calendario")
        from src.scheduler import balance_metrics
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
        st.subheader("🏟️ Pistas utilizadas")
        court_count = Counter(
            m.court.name for m in result.scheduled if m.court
        )
        df_courts = pd.DataFrame(
            {"Pista": list(court_count.keys()), "Partidos": list(court_count.values())}
        )
        st.bar_chart(df_courts.set_index("Pista"))

    # Parejas con más conflictos
    if result.conflict_details:
        st.subheader("👥 Parejas con más conflictos")
        from src.scheduler import pairs_with_most_conflicts
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
    st.title("🔗 Publicar en Syltek")

    from src.syltek_connector import SyltekConnector, run_login_check

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
    st.subheader("Paso 1 — Conectar con Syltek")

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
    st.subheader("Paso 2 — Descubrir pistas disponibles")
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
            st.info(
                "Pistas configuradas con IDs estimados. Si las reservas fallan, "
                "usa el botón de descubrimiento automático."
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
    st.subheader("Paso 3 — Crear reservas en Syltek")

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
        conn.login()
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
        st.subheader("Resultados")
        df_res = pd.DataFrame(st.session_state["syltek_publish_results"])
        st.dataframe(df_res, use_container_width=True)

# (helpers definidos al inicio del archivo)
