"""
Ranking Padel Automator — Interfaz Streamlit
"""
from __future__ import annotations

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

def _df_to_groups(df: pd.DataFrame) -> list[Group]:
    """Convierte un DataFrame de grupos al modelo Group."""
    groups_dict: dict[str, Group] = {}
    for _, row in df.iterrows():
        gid = str(row["group_id"]).strip()
        gname = str(row["group_name"]).strip()
        if gid not in groups_dict:
            groups_dict[gid] = Group(id=gid, name=gname)
        p1 = Player(
            name=str(row["player1_name"]).strip(),
            email=str(row.get("player1_email", "")).strip() or None,
            phone=str(row.get("player1_phone", "")).strip() or None,
        )
        p2 = Player(
            name=str(row["player2_name"]).strip(),
            email=str(row.get("player2_email", "")).strip() or None,
            phone=str(row.get("player2_phone", "")).strip() or None,
        )
        pair = Pair(
            name=str(row["pair_name"]).strip(),
            player_1=p1,
            player_2=p2,
            group_id=gid,
        )
        groups_dict[gid].pairs.append(pair)
    return list(groups_dict.values())


def _df_to_bookings(df: pd.DataFrame) -> list[Booking]:
    """Convierte un DataFrame de reservas al modelo Booking."""
    bookings = []
    for _, row in df.iterrows():
        bookings.append(Booking(
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
        syltek_url = st.text_input("URL de Syltek", value=settings.syltek_url or "")
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
        n_courts = st.slider("Número de pistas disponibles", 1, 12, 4)
        max_per_week = st.slider("Máx. partidos por pareja/semana", 1, 5, 2)
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
                courts = [
                    Court(id=f"court_{i}", name=f"Pista {i}", active=True)
                    for i in range(1, n_courts + 1)
                ]
                phase = RankingPhase(
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
        st.warning(
            "La conexión con Syltek está en desarrollo. "
            "Los selectores CSS deben configurarse en `src/syltek_connector.py`. "
            "Usa los tabs anteriores para cargar datos manualmente mientras tanto."
        )
        st.markdown("""
**Cómo configurar los selectores de Syltek:**

1. Abre Syltek en Chrome con DevTools (F12).
2. Navega a la sección que quieras leer (grupos, reservas...).
3. Usa el botón de inspeccionar elemento para encontrar el selector CSS.
4. Abre `src/syltek_connector.py` y pega los selectores donde dice `<<SELECTOR PENDIENTE>>`.
5. Vuelve aquí y prueba el login en la página de Configuración.
        """)

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

        if st.session_state.matches_generated:
            if st.button("🗓️ Asignar horarios", type="primary"):
                with st.spinner("Asignando horarios... "):
                    scheduler = Scheduler(phase)
                    result = scheduler.schedule(st.session_state.matches)
                st.session_state.schedule_result = result
                st.session_state.matches_scheduled = True
                st.session_state.matches = result.scheduled + result.conflicts

                if result.conflict_count == 0:
                    st.success(f"✅ Todos los partidos asignados ({result.scheduled_count}).")
                else:
                    st.warning(
                        f"⚠️ {result.scheduled_count} partidos programados, "
                        f"{result.conflict_count} con conflictos."
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

    if st.session_state.matches:
        st.subheader("Calendario generado")

        # Filtros
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
                "Observaciones": m.conflict_reason or m.notes or "",
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
        if st.button("Generar Excel", type="primary"):
            with st.spinner("Generando Excel..."):
                path = export_to_excel(result, phase)
            st.success(f"✅ Excel generado: `{path}`")
            with open(path, "rb") as f:
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=f.read(),
                    file_name=path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
            value=settings.syltek_url or "https://padelplus.syltek.com",
            key="syl_url",
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
