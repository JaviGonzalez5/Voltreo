"""
Conector con Padelplus/Syltek usando requests + BeautifulSoup.

Flujo:
  1. login()             → abre sesión HTTP con las credenciales del .env
  2. discover_courts()   → lee el calendario y devuelve {nombre_pista: idResource}
  3. discover_rankings() → lista todos los rankings con sus IDs
  4. get_groups(id)      → lee grupos y equipos de un ranking
  5. create_booking()    → crea una reserva real (solo si dry_run=False)

Seguridad:
  - dry_run=True por defecto: nunca escribe en Syltek sin confirmación explícita.
  - Las contraseñas nunca aparecen en logs.
  - Se detiene si detecta captcha o 2FA.
"""

import base64
import logging
import re
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import settings
from .models import Booking, Court, Group, Pair, Player

logger = logging.getLogger(__name__)

PADELPLUS_BASE = "https://padelplus.padelclick.com"

# Rutas conocidas de Padelplus/Syltek
LOGIN_PATHS = [
    "/system/account/login",
    "/admin/login",
    "/login",
    "/users/login",
]
CALENDAR_PATH = "/bookings/admin/index"


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class SyltekLoginError(Exception):
    pass

class SyltekSecurityStop(Exception):
    pass

class SyltekError(Exception):
    pass


# ---------------------------------------------------------------------------
# Conector principal
# ---------------------------------------------------------------------------

class SyltekConnector:

    def __init__(
        self,
        url: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dry_run: bool = True,
    ):
        raw = (url or settings.syltek_url or PADELPLUS_BASE).rstrip("/")
        # Si el usuario pega la URL de login completa, extraer solo el origen
        for lp in LOGIN_PATHS:
            if raw.endswith(lp):
                raw = raw[: -len(lp)]
                break
        self.base = raw
        self.user = user or settings.syltek_user
        self._password = password or settings.syltek_password
        self.dry_run = dry_run

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
        })
        self._logged_in = False
        self._courts: dict[str, str] = {}      # nombre → idResource
        self._rankings: list[dict] = []        # [{id, nombre, ronda_actual}]

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self) -> tuple[bool, str]:
        """
        Hace login con requests. Devuelve (ok, mensaje).
        Prueba las rutas de login más comunes de Syltek/Padelplus.
        """
        if not self.user or not self._password:
            return False, "Configura SYLTEK_USER y SYLTEK_PASSWORD en el .env"

        login_candidates = [f"{self.base}{p}" for p in LOGIN_PATHS]

        for login_url in login_candidates:
            try:
                r = self._session.get(login_url, timeout=15, allow_redirects=True)
            except requests.RequestException as e:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            form = soup.find("form")
            if not form:
                continue

            # Extraer campos ocultos (tokens CSRF, etc.)
            data: dict[str, str] = {}
            for inp in form.find_all("input"):
                name = inp.get("name", "")
                if name:
                    data[name] = inp.get("value", "")

            # Encontrar campos de usuario y contraseña
            user_inp = (
                form.find("input", {"name": re.compile(r"user|login|email", re.I)}) or
                form.find("input", {"type": ["text", "email"]})
            )
            pass_inp = form.find("input", {"type": "password"})

            if not user_inp or not pass_inp:
                continue

            data[user_inp["name"]] = self.user
            data[pass_inp["name"]] = self._password

            action = form.get("action") or login_url
            if not action.startswith("http"):
                action = self.base + ("" if action.startswith("/") else "/") + action

            try:
                r2 = self._session.post(action, data=data, timeout=15, allow_redirects=True)
            except requests.RequestException as e:
                return False, f"Error de red: {e}"

            # Detectar captcha / 2FA
            lower = r2.text.lower()
            for kw in ["captcha", "recaptcha", "hcaptcha", "two-factor", "2fa"]:
                if kw in lower:
                    raise SyltekSecurityStop(f"Detectado {kw} — intervención manual necesaria.")

            # Comprobar si el login fue exitoso
            if "login" not in r2.url and r2.status_code in (200, 302):
                soup2 = BeautifulSoup(r2.text, "html.parser")
                # Buscar menú admin o nombre de usuario en el header
                admin_indicator = soup2.find(class_=re.compile(
                    r"header|navbar|user-?name|admin|masterHeader", re.I
                ))
                if admin_indicator or "reservas" in r2.text.lower():
                    self._logged_in = True
                    logger.info("Login correcto para %s", self.user)
                    return True, "Login correcto"

        return False, (
            "Login fallido. Comprueba usuario, contraseña y URL en el .env. "
            "Si el problema persiste, abre Syltek en Chrome y copia la URL exacta."
        )

    # ------------------------------------------------------------------
    # Leer disponibilidad real del calendario de Syltek
    # ------------------------------------------------------------------

    def get_bookings_range(
        self,
        from_date: date,
        to_date: date,
        progress_callback=None,
    ) -> list[Booking]:
        """
        Lee el calendario de Syltek día a día entre from_date y to_date.
        Devuelve una lista de Booking con todos los huecos YA OCUPADOS.
        El Scheduler usará esta lista para evitar esos huecos al planificar.

        progress_callback: función opcional que recibe (dias_procesados, total_dias)
        """
        self._assert_logged_in()

        from datetime import timedelta
        bookings: list[Booking] = []
        current = from_date
        total_days = (to_date - from_date).days + 1
        day_num = 0

        while current <= to_date:
            day_bookings = self._get_bookings_for_day(current)
            bookings.extend(day_bookings)
            day_num += 1
            if progress_callback:
                progress_callback(day_num, total_days)
            current += timedelta(days=1)

        logger.info(
            "Leídas %d reservas existentes entre %s y %s",
            len(bookings), from_date, to_date,
        )
        return bookings

    def _get_bookings_for_day(self, day: date) -> list[Booking]:
        """
        Lee el calendario de un día concreto y devuelve las reservas ocupadas.
        """
        encoded = base64.b64encode(day.strftime("%d/%m/%Y").encode()).decode()
        url = f"{self.base}{CALENDAR_PATH}?encodedDate={encoded}&type=56"

        try:
            r = self._session.get(url, timeout=20)
        except requests.RequestException as e:
            logger.warning("Error al leer el calendario del %s: %s", day, e)
            return []

        # Pasamos el HTML crudo (no soup) para evitar que BeautifulSoup
        # altere el contenido de los tags <script>
        try:
            return _parse_occupied_slots(r.text, day)
        except Exception as e:
            logger.warning("Error al parsear reservas del %s: %s", day, e)
            return []

    # ------------------------------------------------------------------
    # Descubrimiento de pistas
    # ------------------------------------------------------------------

    def discover_courts(self, target_date: Optional[date] = None) -> dict[str, str]:
        """
        Navega al calendario y extrae {nombre_pista: idResource}.
        Devuelve el diccionario y lo guarda internamente.
        """
        self._assert_logged_in()

        d = target_date or date.today()
        encoded = base64.b64encode(d.strftime("%d/%m/%Y").encode()).decode()
        url = f"{self.base}/bookings/admin/index?encodedDate={encoded}&type=56"

        try:
            r = self._session.get(url, timeout=15)
        except requests.RequestException as e:
            raise SyltekError(f"Error al cargar el calendario: {e}")

        soup = BeautifulSoup(r.text, "html.parser")
        courts: dict[str, str] = {}

        # 1) Buscar idResource en onclick de celdas (formato más común)
        #    onclick="document.location='/admin/index?...idResource=1480...'"
        #    o a través del callback base64
        for el in soup.find_all(attrs={"onclick": True}):
            onclick = el.get("onclick", "")

            # Buscar idResource directo
            m = re.search(r"idResource['\"]?\s*[:=]\s*['\"]?(\d+)", onclick)
            if m:
                resource_id = m.group(1)
                court_name = _extract_court_name_from_element(el)
                if court_name:
                    courts[court_name] = resource_id
                continue

            # Buscar en callback base64
            m2 = re.search(r"callback=([A-Za-z0-9+/=]+)", onclick)
            if m2:
                try:
                    decoded = base64.b64decode(m2.group(1) + "==").decode("utf-8", errors="ignore")
                    m3 = re.search(r"idResource[=:](\d+)", decoded)
                    if m3:
                        resource_id = m3.group(1)
                        court_name = _extract_court_name_from_element(el)
                        if court_name:
                            courts[court_name] = resource_id
                except Exception:
                    pass

        # 2) Si no encontramos nada por onclick, buscar en el HTML del formulario
        #    cargando la página de nueva reserva para cada columna
        if not courts:
            courts = self._discover_courts_from_form(soup, d)

        # 3) Buscar nombres de columnas en cabeceras de la tabla
        headers = soup.find_all(["th", "td"], class_=re.compile(
            r"timetableGroup|court-?header|column-?name", re.I
        ))
        for h in headers:
            name = h.get_text(strip=True)
            if name and re.match(r"padel|pista|cancha|court", name, re.I):
                # Asociar con el idResource si ya lo tenemos por posición
                idx = headers.index(h)
                if str(idx) in courts:
                    courts[name] = courts.pop(str(idx))

        self._courts = courts
        logger.info("Pistas descubiertas: %s", list(courts.keys()))
        return courts

    def _discover_courts_from_form(self, soup: BeautifulSoup, d: date) -> dict[str, str]:
        """
        Fallback: busca idResource en los atributos data-* de la tabla del horario.
        """
        courts: dict[str, str] = {}
        timetable = soup.find(id=re.compile(r"timetable|schedule|horario", re.I))
        if not timetable:
            timetable = soup.find(class_=re.compile(r"timetable|schedule", re.I))
        if not timetable:
            return courts

        # Buscar celdas con data-resource o data-id
        for cell in timetable.find_all(attrs={"data-resource": True}):
            rid = cell.get("data-resource") or cell.get("data-id")
            name = cell.get("data-name") or cell.get("title") or ""
            if rid and name:
                courts[name] = rid

        return courts

    # ------------------------------------------------------------------
    # Descubrimiento de rankings
    # ------------------------------------------------------------------

    def discover_rankings(self) -> list[dict]:
        """
        Lista todos los rankings disponibles en Syltek.
        Devuelve [{id, nombre, url, ronda_actual}].
        """
        self._assert_logged_in()

        candidates = [
            f"{self.base}/rankings",
            f"{self.base}/activities/rankings",
            f"{self.base}/admin/rankings",
        ]

        for url in candidates:
            try:
                r = self._session.get(url, timeout=15, allow_redirects=True)
                if r.status_code != 200:
                    continue
            except requests.RequestException:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            rankings = _parse_rankings_list(soup, self.base)
            if rankings:
                self._rankings = rankings
                return rankings

        # Intentar buscar desde la sección Actividades
        try:
            r = self._session.get(f"{self.base}/admin", timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            link = soup.find("a", text=re.compile(r"ranking|actividad", re.I))
            if link and link.get("href"):
                href = link["href"]
                if not href.startswith("http"):
                    href = self.base + href
                r2 = self._session.get(href, timeout=15)
                soup2 = BeautifulSoup(r2.text, "html.parser")
                rankings = _parse_rankings_list(soup2, self.base)
                if rankings:
                    self._rankings = rankings
                    return rankings
        except Exception:
            pass

        return []

    def read_all_levels(
        self,
        level_ids: list[int],
        rotation: int,
        progress_callback=None,
    ) -> list[Group]:
        """
        Lee grupos, jugadores y disponibilidades de todos los niveles de ranking.
        URL: /rankings/showtab/{id}/group{rotation}
        Devuelve una lista plana de Group con todas las parejas y su disponibilidad.
        """
        self._assert_logged_in()
        all_groups: list[Group] = []

        for i, rid in enumerate(level_ids):
            url = f"{self.base}/rankings/showtab/{rid}/group{rotation}"
            try:
                r = self._session.get(url, timeout=15)
            except Exception as e:
                logger.warning("Error leyendo nivel %s: %s", rid, e)
                if progress_callback:
                    progress_callback(i + 1, len(level_ids), f"Error en nivel {rid}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            level_name = _extract_ranking_title(soup) or f"Nivel {i+1}"
            groups = _parse_groups_table(soup, str(rid), level_name)
            all_groups.extend(groups)

            if progress_callback:
                n_pairs = sum(len(g.pairs) for g in groups)
                progress_callback(i + 1, len(level_ids), f"{level_name}: {len(groups)} grupos, {n_pairs} parejas")

        return all_groups

    def get_ranking_groups(self, ranking_id: str, round_num: int) -> list[Group]:
        """
        Lee los grupos y equipos de un ranking/rotación desde Syltek.
        URL: /rankings/showtab/{ranking_id}/round{round_num}
        """
        self._assert_logged_in()

        url = f"{self.base}/rankings/showtab/{ranking_id}/round{round_num}"
        try:
            r = self._session.get(url, timeout=15)
        except requests.RequestException as e:
            raise SyltekError(f"Error al cargar el ranking: {e}")

        soup = BeautifulSoup(r.text, "html.parser")
        return _parse_ranking_groups(soup, ranking_id)

    # ------------------------------------------------------------------
    # Crear reserva
    # ------------------------------------------------------------------

    def create_booking(
        self,
        booking_date: date,
        start_hour: int,
        start_minute: int,
        duration_minutes: int,
        court_name: str,
        pair1_name: str,
        pair2_name: str,
        group_name: str = "",
        send_email: bool = False,
    ) -> tuple[bool, str]:
        """
        Crea una reserva en Syltek para un partido de ranking.
        Solo ejecuta si dry_run=False.

        Devuelve (ok, mensaje).
        """
        if self.dry_run:
            label = f"{pair1_name} vs {pair2_name} — {booking_date.strftime('%d/%m/%Y')} {start_hour:02d}:{start_minute:02d} ({court_name})"
            return True, f"[DRY-RUN] Reserva simulada: {label}"

        self._assert_logged_in()

        court_id = self._courts.get(court_name)
        if not court_id:
            return False, (
                f"No se encontró el ID de la pista '{court_name}'. "
                f"Ejecuta 'Descubrir pistas' primero. Pistas conocidas: {list(self._courts.keys())}"
            )

        dt_str = f"{booking_date.day}/{booking_date.month}/{booking_date.year} {start_hour:02d}:{start_minute:02d}"
        client_label = f"{pair1_name} vs {pair2_name}"
        comment = f"Ranking{(' — ' + group_name) if group_name else ''}: {client_label}"

        # GET de la página de nueva reserva para capturar campos ocultos
        form_url = f"{self.base}/admin/newreservation"
        try:
            rg = self._session.get(
                form_url,
                params={"idResource": court_id, "localDatetime": dt_str},
                timeout=15,
            )
        except requests.RequestException as e:
            return False, f"Error al cargar el formulario: {e}"

        soup = BeautifulSoup(rg.text, "html.parser")
        form = soup.find("form")

        # Recoger todos los campos ocultos del formulario
        data: dict[str, str] = {}
        if form:
            for inp in form.find_all("input", type="hidden"):
                name = inp.get("name", "")
                if name:
                    data[name] = inp.get("value", "")

        # Rellenar campos conocidos
        data.update({
            "localDatetime": dt_str,
            "idResource": str(court_id),
            "outstanding": "",
            "setAsPaid": "",
            "fromWeekTimeTable": "false",
            "StartDateHourPicker": str(start_hour),
            "StartDateMinutePicker": f"{start_minute:02d}",
            "duration": str(duration_minutes),
            "numReservations": "1",
            "idReservationTypeGeneral": "",
            "IdCustomer_queryParams": "",
            "IdCustomer": "",
            "metaview_lookup_IdCustomer": client_label,
            "idReservationType": "",
            "comments": comment,
            "sendEmail": "on" if send_email else "",
            "metaview_EntityId": "0",
            "metaview_saveAndNew": "",
        })

        # Determinar acción del formulario
        action = form.get("action", form_url) if form else form_url
        if not action.startswith("http"):
            action = self.base + ("" if action.startswith("/") else "/") + action

        # Enviar el formulario con el botón "Reservar (Pendiente de pago)"
        try:
            rp = self._session.post(
                action,
                data=data,
                timeout=20,
                allow_redirects=True,
                headers={"Referer": form_url},
            )
        except requests.RequestException as e:
            return False, f"Error al enviar el formulario: {e}"

        # Verificar resultado
        if rp.status_code in (200, 302):
            # Buscar señales de éxito o error en la respuesta
            resp_lower = rp.text.lower()
            if any(kw in resp_lower for kw in ["error", "incorrecto", "invalid", "fallo"]):
                snippet = _extract_error_message(BeautifulSoup(rp.text, "html.parser"))
                return False, f"Syltek devolvió un error: {snippet}"
            return True, f"Reserva creada: {client_label} — {booking_date.strftime('%d/%m/%Y')} {start_hour:02d}:{start_minute:02d} en {court_name}"

        return False, f"Error HTTP {rp.status_code} al crear la reserva"

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _assert_logged_in(self) -> None:
        if not self._logged_in:
            raise SyltekLoginError("No has iniciado sesión. Llama a login() primero.")

    def set_courts(self, courts: dict[str, str]) -> None:
        """Permite configurar manualmente el mapa nombre→idResource."""
        self._courts = courts

    def get_known_courts(self) -> dict[str, str]:
        return dict(self._courts)


# ---------------------------------------------------------------------------
# Función síncrona para Streamlit (login check)
# ---------------------------------------------------------------------------

def run_login_check(url: str, user: str, password: str) -> tuple[bool, str]:
    conn = SyltekConnector(url=url, user=user, password=password, dry_run=True)
    return conn.login()


# ---------------------------------------------------------------------------
# Helpers de parsing HTML
# ---------------------------------------------------------------------------

def _parse_occupied_slots(raw_html: str, day: date) -> list[Booking]:
    """
    Parsea la vista diaria del calendario de Syltek.

    Syltek renderiza el horario mediante JavaScript: los datos están en
    el objeto  `var timetable = {...}`  incrustado en el HTML.
    Extraemos resources (pistas) y reservations (reservas) de ese objeto.

    Formato conocido (Padelplus / SCL v10):
      var timetable = {
        resources: {1477:{id:'1477',name:'Padel 1 <br>',...}, ...},
        reservations: {
          12345: {
            start: new Date(2026,3,27,20,30,0),
            end:   new Date(2026,3,27,22,0,0),
            ...,
            idResource: [1477],
          },
          ...
        }
      };
    """
    from datetime import time as dtime, datetime as _dt

    bookings: list[Booking] = []

    # ------------------------------------------------------------------
    # 1. Extraer el bloque "var timetable = { ... };"
    #    Buscamos la primera apertura de llave y contamos hasta cerrar
    # ------------------------------------------------------------------
    m_start = re.search(r'var\s+timetable\s*=\s*\{', raw_html)
    if not m_start:
        logger.debug("No se encontró 'var timetable' en el HTML del día %s", day)
        return bookings

    idx = m_start.start()
    brace = 0
    end_idx = idx
    in_str = False
    str_char = ""
    i = idx
    while i < len(raw_html):
        ch = raw_html[i]
        if in_str:
            if ch == str_char and raw_html[i - 1:i] != "\\":
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace == 0:
                    end_idx = i
                    break
        i += 1

    timetable_js = raw_html[idx: end_idx + 1]
    logger.debug("Bloque timetable extraído: %d chars", len(timetable_js))

    # ------------------------------------------------------------------
    # 2. Extraer pistas (resources)
    #    Soporta: {id:'1477',name:'Padel 1 <br>',...}
    #             {id:"1477",name:"Padel 1",...}
    #             1477:{id:'1477',...}
    # ------------------------------------------------------------------
    resources: dict[str, str] = {}
    for m in re.finditer(
        r"""id\s*:\s*['"]?(\d+)['"]?\s*,\s*name\s*:\s*['"]([^'"]+)['"]""",
        timetable_js,
    ):
        court_id = m.group(1)
        name = re.sub(r'\s*<[^>]+>\s*', ' ', m.group(2)).strip()
        resources[court_id] = name or f"Pista {court_id}"

    # Fallback: clave numérica como key del objeto resources
    if not resources:
        for m in re.finditer(r"(\d{4,5})\s*:\s*\{[^}]*name\s*:\s*'([^']*)'", timetable_js):
            court_id = m.group(1)
            name = re.sub(r'\s*<[^>]+>\s*', ' ', m.group(2)).strip()
            resources[court_id] = name or f"Pista {court_id}"

    logger.debug("Pistas encontradas: %s", resources)

    # ------------------------------------------------------------------
    # 3. Extraer reservas — estrategia robusta en dos pasos:
    #
    #    Paso A: encontrar TODAS las apariciones de "start: new Date(...)"
    #            con posición en el texto.
    #    Paso B: para cada una, buscar "end: new Date(...)" e "idResource:[...]"
    #            en una ventana hacia adelante ANTES de que aparezca el
    #            siguiente "start:". Así evitamos mezclar reservas.
    # ------------------------------------------------------------------
    DATE_RE = re.compile(
        r'start\s*:\s*new\s+Date\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)',
        re.IGNORECASE,
    )
    END_RE = re.compile(
        r'end\s*:\s*new\s+Date\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)',
        re.IGNORECASE,
    )
    RES_RE = re.compile(r'idResource\s*:\s*\[([^\]]*)\]', re.IGNORECASE)

    seen: set[tuple] = set()

    all_starts = list(DATE_RE.finditer(timetable_js))
    for idx_s, m_s in enumerate(all_starts):
        sh = int(m_s.group(4))
        sm = int(m_s.group(5))

        # Ventana: desde el fin de este start hasta el inicio del siguiente start
        # (máximo 1500 chars para robustez)
        win_start = m_s.end()
        win_end   = (all_starts[idx_s + 1].start()
                     if idx_s + 1 < len(all_starts)
                     else min(win_start + 1500, len(timetable_js)))
        window = timetable_js[win_start:win_end]

        m_end = END_RE.search(window)
        m_res = RES_RE.search(window)
        if not m_end or not m_res:
            # Ampliar ventana para buscar idResource (puede estar más lejos)
            wider = timetable_js[win_start: win_start + 2000]
            if not m_end:
                m_end = END_RE.search(wider)
            if not m_res:
                m_res = RES_RE.search(wider)
        if not m_end or not m_res:
            continue

        eh = int(m_end.group(1))
        em = int(m_end.group(2))

        # Validar horas
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            continue

        for court_id in [c.strip() for c in m_res.group(1).split(',') if c.strip().isdigit()]:
            key = (court_id, sh, sm)
            if key in seen:
                continue
            seen.add(key)

            court_name = resources.get(court_id, f"Pista {court_id}")
            try:
                start_dt = _dt.combine(day, dtime(sh, sm))
                end_dt   = _dt.combine(day, dtime(eh, em))
            except ValueError:
                continue

            bookings.append(Booking.model_construct(
                id=str(__import__("uuid").uuid4()),
                court_id=court_id,
                court_name=court_name,
                start_datetime=start_dt,
                end_datetime=end_dt,
                description="Reserva existente",
                source="syltek",
            ))

    logger.debug("Reservas extraídas para %s: %d", day, len(bookings))
    return bookings


def _merge_consecutive_bookings(bookings: list[Booking]) -> list[Booking]:
    """
    Une bloques de 30 min consecutivos de la misma pista en una sola reserva.
    Ej: 17:00-17:30 + 17:30-18:00 → 17:00-18:00
    """
    from datetime import timedelta

    if not bookings:
        return bookings

    # Agrupar por pista
    by_court: dict[str, list[Booking]] = {}
    for b in bookings:
        key = f"{b.court_id}_{b.start_datetime.date()}"
        by_court.setdefault(key, []).append(b)

    merged: list[Booking] = []
    for group in by_court.values():
        group.sort(key=lambda b: b.start_datetime)
        current = group[0]
        for nxt in group[1:]:
            if nxt.start_datetime == current.end_datetime:
                # Extender el bloque actual
                current = Booking.model_construct(
                    id=str(__import__("uuid").uuid4()),
                    court_id=current.court_id,
                    court_name=current.court_name,
                    start_datetime=current.start_datetime,
                    end_datetime=nxt.end_datetime,
                    description=current.description,
                    source="syltek",
                )
            else:
                merged.append(current)
                current = nxt
        merged.append(current)

    return merged


def _extract_court_name_from_element(el) -> str:
    """Intenta extraer el nombre de la pista a partir de un elemento HTML."""
    # Buscar en atributos comunes
    for attr in ("data-name", "data-resource-name", "title", "aria-label"):
        val = el.get(attr, "")
        if val and re.match(r"padel|pista|cancha|court|\d", val, re.I):
            return val.strip()

    # Buscar en el texto del elemento o de su padre
    text = el.get_text(strip=True)
    if text and re.match(r"(padel|pista)\s*\d+", text, re.I):
        return text

    parent = el.find_parent()
    if parent:
        parent_text = parent.get_text(strip=True)
        m = re.search(r"(padel|pista)\s*\d+", parent_text, re.I)
        if m:
            return m.group(0).strip()

    return ""


def _extract_ranking_title(soup: BeautifulSoup) -> str:
    """Extrae el título del ranking (ej. 'Ranking RANKING 2024-205 NIVEL 4')."""
    for tag in ["h1", "h2", "h3", ".page-title", ".ranking-title"]:
        el = soup.select_one(tag) if tag.startswith(".") else soup.find(tag)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return ""


def _parse_groups_table(soup: BeautifulSoup, ranking_id: str, level_name: str) -> list[Group]:
    """
    Parsea los grupos de la página /rankings/showtab/{id}/group{n}.

    Estrategias (en orden):
    1. Cada tabla precedida por encabezado h1-h6 con "Grupo N".
    2. Cada tabla precedida por cualquier elemento con texto corto "Grupo N".
    3. Tabla única con columna "Grupo" en cada fila.
    4. Todas las tablas en orden secuencial (fallback).
    """
    groups: dict[str, Group] = {}
    heading_re = re.compile(r"\bgrupo\s*(\d+)\b", re.I)

    def _register_pair(team_name, player1, player2, group_num, obs):
        from uuid import uuid4 as _u4
        gid   = f"{ranking_id}_G{group_num}"
        gname = f"{level_name} — Grupo {group_num}"
        if gid not in groups:
            groups[gid] = Group.model_construct(id=gid, name=gname, pairs=[])
        avail = parse_observaciones(obs)
        p1 = Player.model_construct(id=str(_u4()), name=player1 or team_name, surname="")
        p2 = Player.model_construct(id=str(_u4()), name=player2 or "", surname="")
        pair = Pair.model_construct(
            id=str(_u4()),
            name=team_name or f"{player1} / {player2}",
            player_1=p1,
            player_2=p2,
            group_id=gid,
            available_weekdays=avail["weekdays"],
            available_from=avail["available_from"],
            available_until=avail["available_until"],
            availability_notes=obs,
            preferred_weekday=avail["preferred_weekday"],
            preferred_time=avail["preferred_time"],
            manual_only=avail.get("manual_only", False),
        )
        groups[gid].pairs.append(pair)

    def _parse_table(table, fallback_group_num):
        rows = table.find_all("tr")
        if not rows:
            return
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]
        col = {
            "equipo": _find_col(headers, ["equipo", "team", "pareja"]),
            "j1":     _find_col(headers, ["jugador1", "jugador 1", "player1", "j1"]),
            "j2":     _find_col(headers, ["jugador2", "jugador 2", "player2", "j2"]),
            "grupo":  _find_col(headers, ["grupo", "group"]),
            "obs":    _find_col(headers, ["observaciones", "obs", "notas", "notes"]),
        }
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            def cell(idx):
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx].get_text(strip=True)
            team_name = cell(col["equipo"])
            player1   = cell(col["j1"])
            player2   = cell(col["j2"])
            obs       = cell(col["obs"])
            group_num = cell(col["grupo"]) or str(fallback_group_num)
            if not team_name and not player1:
                continue
            _register_pair(team_name, player1, player2, group_num, obs)

    visited: set[int] = set()

    # --- Estrategia 1: headings h1-h6 con "Grupo N" → find_next("table") ---
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        m = heading_re.search(tag.get_text(strip=True))
        if not m:
            continue
        gnum = int(m.group(1))
        tbl = tag.find_next("table")
        if tbl and id(tbl) not in visited:
            visited.add(id(tbl))
            _parse_table(tbl, gnum)

    if groups:
        return list(groups.values())

    # --- Estrategia 2: cualquier elemento con texto exacto "Grupo N" (≤25 chars) ---
    for tag in soup.find_all(True):
        txt = tag.get_text(strip=True)
        if len(txt) > 25:
            continue
        m = heading_re.search(txt)
        if not m:
            continue
        gnum = int(m.group(1))
        tbl = tag.find_next("table")
        if tbl and id(tbl) not in visited:
            visited.add(id(tbl))
            _parse_table(tbl, gnum)

    if groups:
        return list(groups.values())

    # --- Estrategia 3 & 4: tabla única con columna "Grupo", o todas en orden ---
    all_tables = soup.find_all("table")
    for idx, tbl in enumerate(all_tables, start=1):
        if id(tbl) in visited:
            continue
        visited.add(id(tbl))
        _parse_table(tbl, idx)

    return list(groups.values())


def _find_col(headers: list[str], candidates: list[str]) -> Optional[int]:
    """Devuelve el índice de la primera columna que coincide con algún candidato."""
    for i, h in enumerate(headers):
        for c in candidates:
            if c in h:
                return i
    return None


def parse_observaciones(text: str) -> dict:
    """
    Parsea el campo Observaciones de Syltek para extraer disponibilidad.
    Devuelve {
      'weekdays': [0..6],
      'available_from': time|None,
      'available_until': time|None,
      'preferred_weekday': int|None,   # pista fija: día preferido
      'preferred_time': time|None,     # pista fija: hora preferida
    }

    Ejemplos soportados:
      L A V 1630 A 2030  →  lunes-viernes, 16:30-20:30
      L - J 19 a 21      →  lunes-jueves, 19:00-21:00
      M , J +19-21       →  martes y jueves, 19:00-21:00
      PF X2030           →  pista fija miércoles 20:30
      PF J 1930          →  pista fija jueves 19:30
      L Y X, M, J Y V HASTA LAS 1800  →  L,M,X,J,V hasta 18:00
      +1930              →  desde las 19:30 cualquier día
    """
    from datetime import time as dtime

    if not text or not text.strip():
        return {"weekdays": [], "available_from": None, "available_until": None,
                "preferred_weekday": None, "preferred_time": None,
                "manual_only": False}

    t = text.upper().strip()

    # -----------------------------------------------------------------------
    # Detectar texto de asignación manual (ej: "MIRAR MAIL", "PENDIENTE"…)
    # Si el texto NO contiene ningún día reconocible ni ninguna hora,
    # se trata de una nota y el partido se deja para asignación manual.
    # -----------------------------------------------------------------------
    _has_any_day  = bool(re.search(r"(?<![A-Z])([LMXJVSD])(?![A-Z])", t))
    _has_any_time = bool(re.search(r"\b\d{4}\b|\+\d{2,4}|\bPF\b", t))
    if not _has_any_day and not _has_any_time:
        return {
            "weekdays": [], "available_from": None, "available_until": None,
            "preferred_weekday": None, "preferred_time": None,
            "manual_only": True,
        }

    # Mapa de abreviaturas de días
    DMAP = {"L": 0, "M": 1, "X": 2, "J": 3, "V": 4, "S": 5, "D": 6}

    weekdays: set[int] = set()
    preferred_weekday = None
    preferred_time = None

    # Pista fija: "PF X2030", "PF J 1930", "PF M2100"
    pf_match = re.search(r"\bPF\s+([LMXJVSD])\s*(\d{3,4})\b", t)
    if pf_match:
        preferred_weekday = DMAP.get(pf_match.group(1))
        h_str = pf_match.group(2)
        preferred_time = (dtime(int(h_str[:2]), int(h_str[2:])) if len(h_str) == 4
                          else dtime(int(h_str), 0)) if h_str.isdigit() else None

    # Fin de semana (sin PF de pista fija)
    if re.search(r"\bFINDE\b|\bFIN\s+DE\s+SEMANA\b", t):
        weekdays.update([5, 6])

    # Rangos: "L A V", "L - J", "L A J"
    for m in re.finditer(r"\b([LMXJVSD])\s*(?:\bA\b|-)\s*([LMXJVSD])\b", t):
        s = DMAP.get(m.group(1))
        e = DMAP.get(m.group(2))
        if s is not None and e is not None:
            weekdays.update(range(s, e + 1) if s <= e else list(range(s, 7)) + list(range(0, e + 1)))

    # Días sueltos: "M , J", "L Y X, M, J Y V"
    for m in re.finditer(r"(?<![A-Z])([LMXJVSD])(?![A-Z0-9])", t):
        d = DMAP.get(m.group(1))
        if d is not None:
            weekdays.add(d)

    # Patrón día+hora pegados sin espacio: "L1930", "M2100", "J2030"
    # (la regex de días sueltos los ignora porque el día va seguido de un dígito)
    for m in re.finditer(r"(?<![A-Z])([LMXJVSD])(\d{4})\b", t):
        d_code = DMAP.get(m.group(1))
        if d_code is not None:
            weekdays.add(d_code)

    # Parsear horas
    available_from = None
    available_until = None

    def _make_time(h: int, m: int) -> Optional[dtime]:
        try:
            return dtime(h, m) if 0 <= h <= 23 and 0 <= m <= 59 else None
        except ValueError:
            return None

    def _parse_hhmm(s: str) -> Optional[dtime]:
        s = s.strip()
        if len(s) == 4 and s.isdigit():
            return _make_time(int(s[:2]), int(s[2:]))
        if len(s) <= 2 and s.isdigit():
            return _make_time(int(s), 0)
        return None

    # Negaciones: "L NO", "M NO", etc. — el día aparece explícitamente EXCLUIDO
    negated: set[int] = set()
    for nm in re.finditer(r"(?<![A-Z])([LMXJVSD])\s+NO\b", t):
        d_neg = DMAP.get(nm.group(1))
        if d_neg is not None:
            negated.add(d_neg)

    if negated:
        if not weekdays or weekdays.issubset(negated):
            # Todos los días encontrados son negados (o no había días positivos)
            # → significa "todos los días EXCEPTO los negados"
            weekdays = set(range(7)) - negated
        else:
            weekdays -= negated

    # +HHMM, +HHH, +HH  (acepta horas de 2 dígitos como +18, +21)
    m = re.search(r"\+\s*(\d{2,4})", t)
    if m:
        available_from = _parse_hhmm(m.group(1))

    # "HH:MM A HH:MM" o "HHMM A HHMM" o "HH A HH"
    m = re.search(r"\b(\d{2,4})\s+A\s+(\d{2,4})\b", t)
    if m:
        tf = _parse_hhmm(m.group(1))
        tu = _parse_hhmm(m.group(2))
        if tf and (available_from is None):
            available_from = tf
        if tu:
            available_until = tu

    # "HASTA LAS HHMM" o "HASTA HHMM"
    m = re.search(r"HASTA\s+(?:LAS\s+)?(\d{3,4})", t)
    if m and available_until is None:
        available_until = _parse_hhmm(m.group(1))

    # Número de 4 dígitos suelto tipo "1930", "1800", "2100"
    if available_from is None:
        nums = re.findall(r"\b(1[6-9]\d{2}|2[0-2]\d{2})\b", t)
        if nums:
            available_from = _parse_hhmm(nums[0])

    # -----------------------------------------------------------------------
    # Caso "DÍA HORA" exacto: "L 1930", "M2100", "J 2030"
    # Si hay exactamente UN día y UNA hora sin rango ("A") ni prefijo "+",
    # significa "solo puedo jugar ESE día A ESA hora".
    # → Fijar ventana de 2 horas y marcar como preferred.
    # -----------------------------------------------------------------------
    _has_day_range  = bool(re.search(r"[LMXJVSD]\s*(?:\bA\b|-)\s*[LMXJVSD]", t))
    _has_time_range = bool(re.search(r"\b\d{2,4}\s+A\s+\d{2,4}\b", t))
    _has_plus       = bool(re.search(r"\+\s*\d{2,4}", t))

    if (
        available_from is not None
        and available_until is None
        and len(weekdays) == 1
        and not _has_day_range
        and not _has_time_range
        and not _has_plus
    ):
        from datetime import timedelta, datetime as _dt2
        _until = (
            _dt2.combine(_dt2.today().date(), available_from) + timedelta(hours=2)
        ).time()
        available_until = _until
        # Marcar como preferred (pista fija implícita)
        if preferred_weekday is None:
            preferred_weekday = next(iter(weekdays))
        if preferred_time is None:
            preferred_time = available_from

    return {
        "weekdays": sorted(weekdays),
        "available_from": available_from,
        "available_until": available_until,
        "preferred_weekday": preferred_weekday,
        "preferred_time": preferred_time,
        "manual_only": False,
    }


def _parse_rankings_list(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extrae la lista de rankings de una página HTML."""
    rankings = []

    # Buscar links a rankings
    for link in soup.find_all("a", href=re.compile(r"/rankings/", re.I)):
        href = link.get("href", "")
        m = re.search(r"/rankings/showtab/(\d+)", href)
        if not m:
            m = re.search(r"/rankings/(\d+)", href)
        if not m:
            continue

        ranking_id = m.group(1)
        name = link.get_text(strip=True) or f"Ranking {ranking_id}"

        # Evitar duplicados
        if any(r["id"] == ranking_id for r in rankings):
            continue

        rankings.append({
            "id": ranking_id,
            "nombre": name,
            "url": f"{base_url}/rankings/showtab/{ranking_id}/round1",
            "ronda_actual": 1,
        })

    return rankings


def _parse_ranking_groups(soup: BeautifulSoup, ranking_id: str) -> list[Group]:
    """
    Parsea los grupos y equipos de la página de rotación de un ranking.
    Página: /rankings/showtab/{id}/round{n}
    """
    groups: list[Group] = []

    # Buscar secciones de grupos (típicamente "Grupo 1", "Grupo 2"...)
    group_headers = soup.find_all(
        string=re.compile(r"grupo\s*\d+", re.I)
    )

    if not group_headers:
        # Intentar por tabla directamente
        tables = soup.find_all("table")
        for i, table in enumerate(tables):
            group = _parse_group_table(table, f"Grupo {i+1}", ranking_id)
            if group and group.pairs:
                groups.append(group)
        return groups

    for header_text in group_headers:
        parent = getattr(header_text, "parent", None)
        if not parent:
            continue
        # Buscar la tabla más cercana después de este header
        table = parent.find_next("table")
        if not table:
            container = parent.find_parent()
            if container:
                table = container.find("table")

        if table:
            group_name = re.sub(r"\s+", " ", header_text.strip())
            group = _parse_group_table(table, group_name, ranking_id)
            if group and group.pairs:
                groups.append(group)

    return groups


def _parse_group_table(table, group_name: str, ranking_id: str) -> Optional[Group]:
    """Extrae parejas/equipos de una tabla de ranking."""
    from uuid import uuid4 as _u4
    gid = f"{ranking_id}_{group_name.replace(' ', '_')}"
    group = Group.model_construct(id=gid, name=group_name, pairs=[])

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        team_cell = None
        for cell in cells:
            text = cell.get_text(strip=True)
            if re.search(r"[A-ZÁÉÍÓÚ][a-záéíóú]+-\s*[A-ZÁÉÍÓÚ]", text):
                team_cell = cell
                break

        if not team_cell:
            continue

        team_name = team_cell.get_text(strip=True)
        parts = re.split(r"-\s*", team_name, maxsplit=1)
        if len(parts) == 2:
            p1 = Player.model_construct(id=str(_u4()), name=parts[0].strip(), surname="")
            p2 = Player.model_construct(id=str(_u4()), name=parts[1].strip(), surname="")
        else:
            p1 = Player.model_construct(id=str(_u4()), name=team_name, surname="")
            p2 = Player.model_construct(id=str(_u4()), name="", surname="")

        pair = Pair.model_construct(
            id=str(_u4()),
            name=team_name,
            player_1=p1,
            player_2=p2,
            group_id=group.id,
            available_weekdays=[],
            available_from=None,
            available_until=None,
            availability_notes="",
            preferred_weekday=None,
            preferred_time=None,
        )
        group.pairs.append(pair)

    return group


def _extract_error_message(soup: BeautifulSoup) -> str:
    """Extrae el mensaje de error más relevante de una página de respuesta."""
    for selector in [".error", ".alert", ".alert-danger", "#error", ".errorMessage"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)[:200]
    return soup.get_text(strip=True)[:200]
