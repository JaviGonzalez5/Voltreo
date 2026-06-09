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
import time
import uuid as _uuid_mod
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import settings
from .models import Booking, Court, Group, Pair, Player

logger = logging.getLogger(__name__)

PADELPLUS_BASE = "https://padelplus.syltek.com"

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
        # Días que NO se pudieron leer (red/parseo) tras los reintentos. Se exponen
        # para avisar al usuario: si esta lista no está vacía el total es PARCIAL,
        # lo que explicaba que cada importación devolviera un número distinto.
        self.last_failed_days: list[date] = []
        current = from_date
        total_days = (to_date - from_date).days + 1
        day_num = 0

        while current <= to_date:
            try:
                bookings.extend(self._get_bookings_for_day(current))
            except Exception as e:
                self.last_failed_days.append(current)
                logger.warning("Día %s no leído (se omite del total): %s", current, e)
            day_num += 1
            if progress_callback:
                progress_callback(day_num, total_days)
            current += timedelta(days=1)

        logger.info(
            "Leídas %d reservas entre %s y %s (%d día(s) fallidos)",
            len(bookings), from_date, to_date, len(self.last_failed_days),
        )
        return bookings

    def _get_bookings_for_day(self, day: date, _attempts: int = 3) -> list[Booking]:
        """
        Lee el calendario de un día concreto y devuelve las reservas ocupadas.

        Reintenta ante errores de red (timeout, conexión, 5xx) para que un fallo
        intermitente no haga desaparecer las reservas de ese día — la causa de que
        el total variara entre importaciones. Si tras los reintentos sigue fallando,
        lanza SyltekError para que el día se registre como fallido (no como 0).
        """
        encoded = base64.b64encode(day.strftime("%d/%m/%Y").encode()).decode()
        url = f"{self.base}{CALENDAR_PATH}?encodedDate={encoded}&type=56"

        last_err = None
        for _attempt in range(max(1, _attempts)):
            try:
                r = self._session.get(url, timeout=20)
                r.raise_for_status()
            except requests.RequestException as e:
                last_err = e
                time.sleep(0.5 * (_attempt + 1))  # backoff progresivo
                continue
            # Pasamos el HTML crudo (no soup) para no alterar los <script>.
            # Un error de parseo no se arregla reintentando → no reintentar.
            try:
                return _parse_occupied_slots(r.text, day)
            except Exception as e:
                last_err = e
                break

        raise SyltekError(
            f"No se pudo leer el calendario del {day} tras {_attempts} intento(s): {last_err}"
        )

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

def _balanced_block(text: str, open_idx: int) -> "tuple[str, int]":
    """
    Dado un índice que apunta a un '{', devuelve (contenido_interior, idx_del_cierre).
    Respeta strings con comillas simples/dobles y escapes. Determinista.
    """
    brace = 0
    in_str = False
    str_char = ""
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == str_char:
                bs = 0
                j = i - 1
                while j >= 0 and text[j] == "\\":
                    bs += 1
                    j -= 1
                if bs % 2 == 0:
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
                    return text[open_idx + 1:i], i
        i += 1
    return text[open_idx + 1:], n - 1


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
            # Comprobar si el carácter está escapado.
            # Contar barras invertidas consecutivas antes del índice actual:
            # si es impar, el carácter está escapado y no cierra el string.
            if ch == str_char:
                num_backslashes = 0
                j = i - 1
                while j >= idx and raw_html[j] == "\\":
                    num_backslashes += 1
                    j -= 1
                if num_backslashes % 2 == 0:  # par (o cero) → no está escapado
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
    # 3. Extraer reservas — parseo ESTRUCTURAL (determinista).
    #
    #    En vez de ventanas posicionales (cuyo resultado dependía del orden
    #    de las claves JSON y producía conteos distintos entre escaneos),
    #    localizamos el bloque `reservations: { ... }` y separamos cada
    #    reserva por emparejamiento de llaves. Cada reserva se parsea de
    #    forma aislada → mismo HTML siempre da el mismo resultado.
    # ------------------------------------------------------------------
    START_RE = re.compile(
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

    # Localizar el bloque reservations
    m_res_block = re.search(r'reservations\s*:\s*\{', timetable_js)
    reservation_chunks: list[str] = []
    if m_res_block:
        open_idx = timetable_js.index("{", m_res_block.end() - 1)
        inner, _ = _balanced_block(timetable_js, open_idx)
        # Cada entrada de reservations es  KEY: { ... }  → un bloque balanceado
        k = 0
        while True:
            ob = inner.find("{", k)
            if ob == -1:
                break
            content, close = _balanced_block(inner, ob)
            reservation_chunks.append(content)
            k = close + 1
    else:
        # Fallback: si no hay bloque reservations reconocible, trocear por "start:"
        starts = list(START_RE.finditer(timetable_js))
        for i, ms in enumerate(starts):
            seg_end = starts[i + 1].start() if i + 1 < len(starts) else len(timetable_js)
            reservation_chunks.append(timetable_js[ms.start():seg_end])

    seen: set[tuple] = set()
    for chunk in reservation_chunks:
        m_s = START_RE.search(chunk)
        m_e = END_RE.search(chunk)
        m_r = RES_RE.search(chunk)
        if not (m_s and m_e and m_r):
            continue

        sh, sm = int(m_s.group(4)), int(m_s.group(5))
        eh, em = int(m_e.group(1)), int(m_e.group(2))
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            continue

        try:
            start_dt = _dt.combine(day, dtime(sh, sm))
            end_dt   = _dt.combine(day, dtime(eh, em))
        except ValueError:
            continue

        for court_id in [c.strip() for c in m_r.group(1).split(",") if c.strip().isdigit()]:
            # Clave con inicio Y fin → no se pierden reservas distintas con el mismo inicio
            key = (court_id, start_dt, end_dt)
            if key in seen:
                continue
            seen.add(key)
            bookings.append(Booking.model_construct(
                id=str(_uuid_mod.uuid4()),
                court_id=court_id,
                court_name=resources.get(court_id, f"Pista {court_id}"),
                start_datetime=start_dt,
                end_datetime=end_dt,
                description="Reserva existente",
                source="syltek",
            ))

    # Orden determinista para que dos escaneos del mismo HTML sean idénticos
    bookings.sort(key=lambda b: (b.court_id, b.start_datetime, b.end_datetime))
    logger.debug("Reservas extraídas para %s: %d (de %d bloques)",
                 day, len(bookings), len(reservation_chunks))
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
                    id=str(_uuid_mod.uuid4()),
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
            per_day_windows=avail.get("per_day_windows", {}),
            availability_notes=obs,
            preferred_weekday=avail["preferred_weekday"],
            preferred_time=avail["preferred_time"],
            preferred_slots=avail.get("preferred_slots", []),
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
      'weekdays':         [0..6],            # días disponibles (0=Lun…6=Dom)
      'available_from':   time|None,         # hora mínima global (fallback)
      'available_until':  time|None,         # hora máxima de INICIO (inclusiva) global
      'per_day_windows':  {int: {"from":time|None,"until":time|None}},
      'preferred_weekday': int|None,
      'preferred_time':    time|None,
      'preferred_slots':   [{"weekday":int,"time":time}, ...],
      'manual_only':       bool,
    }

    Semántica clave
    ─────────────────────────────────────────────────────────────
    · HORA EXACTA  "L 1930"   → lunes SOLO a las 19:30
                               (available_from=19:30, available_until=19:30)
    · DESDE        "L +1930"  → lunes desde 19:30 en adelante
                               (available_from=19:30, available_until=None)
    · RANGO        "L 18-2030"→ lunes inicio entre 18:00 y 20:30 (inclusivo)
                               (available_from=18:00, available_until=20:30)
    · HASTA        "HASTA LAS 1800" → inicio ≤ 18:00
    · "available_until" siempre es hora máxima de INICIO (inclusiva).
      El scheduler usa  st > available_until  para bloquear.

    Casos especiales
    ─────────────────────────────────────────────────────────────
    · "J+230"  → autocorregido a  "J+2030"
    · PF variantes: PF X2030 / PFIJA X 2000H / PF JUE 20:00
    · PF override: aunque el horario general sea "desde 21:00",
      el slot PF (ej. X 20:00) siempre queda como ventana válida.
    · "L-V" sin hora → lunes a viernes, sin restricción horaria.
    · Días en 3 letras: LUN MAR MIE JUE VIE SAB DOM.
    """
    from datetime import time as dtime, timedelta, datetime as _dt2

    if not text or not text.strip():
        return {
            "weekdays": [], "available_from": None, "available_until": None,
            "per_day_windows": {},
            "preferred_weekday": None, "preferred_time": None,
            "preferred_slots": [],
            "manual_only": False,
        }

    t = text.upper().strip()

    # ── Autocorrección: "J+230" → "J+2030", "+230" → "+2030"
    # Horas de 3 dígitos tras "+" → anteponer "2" si empieza por 0-9 y ≤ 959
    def _fix_3digit_hours(s: str) -> str:
        def _fix(m):
            digits = m.group(1)
            # 3 dígitos como "230" → "2030", "900" → "0900" no es válido; tratar como "2030"
            if len(digits) == 3:
                # Posibles: 130=1:30? 200=2:00? 900=9:00? 230=20:30 es lo más frecuente
                # Si primer dígito es 1-9 y el número ≤ 959 → probable hora media:
                # "230" más probable es "2030" (20:30) que "2:30"
                if digits[0] in "123456789" and int(digits) <= 959:
                    # Insertar "20" prefix solo si parece minutos (último 2 dígitos ≤ 59)
                    if int(digits[1:]) <= 59:
                        return m.group(0).replace(digits, "20" + digits[-2:] if digits[0] == "2" else "2" + digits)
            return m.group(0)
        return re.sub(r"\+\s*(\d{3})\b", _fix, s)

    t = _fix_3digit_hours(t)

    # ── Normalizar días en 3 letras → 1 letra
    THREE_LETTER = {
        "LUN": "L", "MAR": "M", "MIE": "X", "MIÉ": "X", "JUE": "J",
        "VIE": "V", "SAB": "S", "SÁB": "S", "DOM": "D",
    }
    for long, short in THREE_LETTER.items():
        t = re.sub(r"\b" + long + r"\b", short, t)

    # ── Mapa de abreviaturas de días
    DMAP = {"L": 0, "M": 1, "X": 2, "J": 3, "V": 4, "S": 5, "D": 6}

    # ── Detectar texto de asignación manual
    _has_any_day  = bool(re.search(r"(?<![A-Z])([LMXJVSD])(?![A-Z])", t))
    _has_any_time = bool(re.search(r"\b\d{3,4}\b|\+\d{2,4}|\bPF", t))
    if not _has_any_day and not _has_any_time:
        return {
            "weekdays": [], "available_from": None, "available_until": None,
            "per_day_windows": {},
            "preferred_weekday": None, "preferred_time": None,
            "preferred_slots": [],
            "manual_only": True,
        }

    # ── Helpers de tiempo
    def _make_time(h: int, m: int) -> Optional[dtime]:
        try:
            return dtime(h, m) if 0 <= h <= 23 and 0 <= m <= 59 else None
        except ValueError:
            return None

    def _parse_hhmm(s: str) -> Optional[dtime]:
        s = s.strip()
        if len(s) == 4 and s.isdigit():
            return _make_time(int(s[:2]), int(s[2:]))
        if len(s) == 3 and s.isdigit():
            return _make_time(int(s[0]), int(s[1:]))
        if len(s) <= 2 and s.isdigit():
            return _make_time(int(s), 0)
        # "HH:MM"
        mm = re.match(r"^(\d{1,2}):(\d{2})$", s)
        if mm:
            return _make_time(int(mm.group(1)), int(mm.group(2)))
        return None

    def _parse_time_token(tok: str) -> Optional[dtime]:
        """Parsea un token de hora: "1930", "19:30", "19", "193021"→19:30."""
        tok = tok.strip()
        # 6 dígitos HHMM+SS → tomar primeros 4
        if len(tok) == 6 and tok.isdigit():
            tok = tok[:4]
        return _parse_hhmm(tok)

    # ═══════════════════════════════════════════════════════
    # PISTA FIJA (PF)
    # Formatos: PF X2030 / PFIJA X 2000H / PF JUE 20:00 / PF L 20:30
    # ═══════════════════════════════════════════════════════
    preferred_weekday: Optional[int] = None
    preferred_time: Optional[dtime]  = None
    preferred_slots: list[dict] = []
    _seen_pf_slots: set[tuple[int, dtime]] = set()

    pf_patterns = [
        # PFIJA / PF seguido de día y hora
        r"PF(?:IJA|IXA)?\s+([LMXJVSD])\s*([\d:]+)H?",
        # con hora separada
        r"PF(?:IJA|IXA)?\s+([LMXJVSD])\s+(\d{3,4})\b",
    ]
    for pp in pf_patterns:
        for pm in re.finditer(pp, t):
            _pf_wd = DMAP.get(pm.group(1))
            _pf_time = _parse_time_token(pm.group(2))
            if _pf_wd is None or _pf_time is None:
                continue
            _pf_key = (_pf_wd, _pf_time)
            if _pf_key in _seen_pf_slots:
                continue
            _seen_pf_slots.add(_pf_key)
            preferred_slots.append({"weekday": _pf_wd, "time": _pf_time})

    # Compatibilidad: mantener preferred_weekday/preferred_time como la primera PF detectada.
    if preferred_slots:
        preferred_weekday = preferred_slots[0]["weekday"]
        preferred_time = preferred_slots[0]["time"]

    # ═══════════════════════════════════════════════════════
    # SEGMENTACIÓN POR SEGMENTOS
    # Dividir el texto en segmentos separados por ; . \n
    # y procesar cada uno extrayendo (días, ventana horaria).
    # ═══════════════════════════════════════════════════════

    # Eliminar la parte PF del texto para no confundir el parser
    t_clean = re.sub(r"PF(?:IJA|IXA)?\s+[LMXJVSD]\s*[\d:H]+", "", t)
    t_clean = re.sub(r"PF(?:IJA|IXA)?\s+[LMXJVSD]\s+\d{3,4}", "", t_clean)
    # También eliminar "SAB +XXXX" y "DOM" (fines de semana — filtrados al final)
    # No los eliminamos para que los días se detecten y luego se filtren

    per_day_windows: dict[int, dict] = {}
    weekdays_set: set[int] = set()

    def _apply_window(days: list, tf: Optional[dtime], tu: Optional[dtime]) -> None:
        for d in days:
            weekdays_set.add(d)
            per_day_windows[d] = {"from": tf, "until": tu}

    def _parse_segment(seg: str) -> None:
        """Parsea un segmento de texto y registra ventanas por día."""
        seg = seg.strip()
        if not seg:
            return

        # Extraer días del segmento
        seg_days: list[int] = []

        # Patrón 1: día+rango inmediato sin espacio "X18-21", "X 18-21"
        # Captura (día)(hh-hh) o (día)(hhmm-hhmm)
        day_range_direct = re.findall(
            r"(?<![A-Z])([LMXJVSD])\s+(\d{2,4})-(\d{2,4})\b", seg
        )
        # Patrón 2: día+rango pegado sin espacio (X18-21)
        day_range_direct2 = re.findall(
            r"(?<![A-Z])([LMXJVSD])(\d{2,4})-(\d{2,4})\b", seg
        )
        # Patrón 3: DÍA HHMM+2dígitos "M193021"
        day_time_range_6 = re.findall(
            r"(?<![A-Z])([LMXJVSD])\s*(\d{4})(\d{2})\b", seg
        )
        # Patrón 4: DÍA + 4 dígitos exactos (pegado o con espacio) "L1930" "L 1930"
        day_exact_4 = re.findall(
            r"(?<![A-Z])([LMXJVSD])\s+(\d{4})\b(?!\s*-)", seg
        )
        day_exact_4_nospace = re.findall(
            r"(?<![A-Z])([LMXJVSD])(\d{4})\b(?!\s*-)", seg
        )
        # Patrón 5: rango de días "L-V", "L A V"
        day_day_ranges = re.findall(
            r"(?<![A-Z])([LMXJVSD])\s*(?:-|(?:\bA\b))\s*([LMXJVSD])(?![A-Z0-9])", seg
        )

        handled_days_in_seg: set[int] = set()

        # Patrón 0: DÍA+PLUS "L+1930", "J+2030"  ← ANTES que cualquier otro
        day_plus_pairs = re.findall(r"(?<![A-Z])([LMXJVSD])\+\s*(\d{2,4})\b", seg)
        for d_ch, ht in day_plus_pairs:
            d = DMAP.get(d_ch)
            tf = _parse_hhmm(ht)
            if d is not None and tf:
                _apply_window([d], tf, None)
                handled_days_in_seg.add(d)

        # Patrón 2b: GRUPO de días con coma/Y seguido de rango "X,J,V 18-21", "J,V 18-20"
        for grp_m in re.finditer(
            r"(?<![A-Z])([LMXJVSD](?:\s*[,Y]\s*[LMXJVSD])+)\s+(\d{2,4})-(\d{2,4})\b", seg
        ):
            grp_str = grp_m.group(1)
            tf = _parse_hhmm(grp_m.group(2))
            tu = _parse_hhmm(grp_m.group(3))
            if tf and tu:
                for d_ch in re.findall(r"[LMXJVSD]", grp_str):
                    d = DMAP.get(d_ch)
                    if d is not None and d not in handled_days_in_seg:
                        _apply_window([d], tf, tu)
                        handled_days_in_seg.add(d)

        # Patrón 2c: GRUPO de días con coma/Y seguido de + hora "L,M +18"
        for grp_m in re.finditer(
            r"(?<![A-Z])([LMXJVSD](?:\s*[,Y]\s*[LMXJVSD])+)\s*\+\s*(\d{2,4})\b", seg
        ):
            grp_str = grp_m.group(1)
            tf = _parse_hhmm(grp_m.group(2))
            if tf:
                for d_ch in re.findall(r"[LMXJVSD]", grp_str):
                    d = DMAP.get(d_ch)
                    if d is not None and d not in handled_days_in_seg:
                        _apply_window([d], tf, None)
                        handled_days_in_seg.add(d)

        # Procesar DÍA+RANGO (más específico primero)
        for d_ch, h1, h2 in day_range_direct + day_range_direct2:
            d = DMAP.get(d_ch)
            tf = _parse_hhmm(h1)
            tu = _parse_hhmm(h2)
            if d is not None and tf and tu:
                _apply_window([d], tf, tu)
                handled_days_in_seg.add(d)

        # Procesar DÍA+6dígitos "M193021" → M 19:30-21:00
        for d_ch, h4, h2 in day_time_range_6:
            d  = DMAP.get(d_ch)
            tf = _parse_hhmm(h4)
            tu = _make_time(int(h2), 0)
            if d is not None and tf and tu and d not in handled_days_in_seg:
                _apply_window([d], tf, tu)
                handled_days_in_seg.add(d)

        # Procesar DÍA+4dígitos exacto
        for d_ch, h4 in day_exact_4 + day_exact_4_nospace:
            d  = DMAP.get(d_ch)
            tt = _parse_hhmm(h4)
            if d is not None and tt and d not in handled_days_in_seg:
                _apply_window([d], tt, tt)  # exacto: from==until
                handled_days_in_seg.add(d)

        # Extraer días de rangos de días "L-V"
        for d1_ch, d2_ch in day_day_ranges:
            s_d = DMAP.get(d1_ch)
            e_d = DMAP.get(d2_ch)
            if s_d is not None and e_d is not None:
                r_days = (list(range(s_d, e_d + 1)) if s_d <= e_d
                          else list(range(s_d, 7)) + list(range(0, e_d + 1)))
                for d in r_days:
                    if d not in handled_days_in_seg:
                        seg_days.append(d)

        # Días sueltos (no cubiertos por patrones anteriores)
        for m in re.finditer(r"(?<![A-Z])([LMXJVSD])(?![A-Z0-9-])", seg):
            d = DMAP.get(m.group(1))
            if d is not None and d not in handled_days_in_seg:
                # Asegurarse de que no está cubierto por un rango de días en el segmento
                in_range = any(
                    s_d_ch is not None and e_d_ch is not None and
                    (min(DMAP[s_d_ch], DMAP[e_d_ch]) <= d <= max(DMAP[s_d_ch], DMAP[e_d_ch]))
                    for s_d_ch, e_d_ch in day_day_ranges
                    if s_d_ch in DMAP and e_d_ch in DMAP
                )
                if not in_range:
                    seg_days.append(d)

        if not seg_days and not handled_days_in_seg:
            return  # Segmento sin días reconocibles

        # Extraer ventana de tiempo del segmento (para días aún sin ventana)
        # Orden de prioridad: + (desde), rango, HASTA, 4 dígitos sueltos
        tf_seg: Optional[dtime] = None
        tu_seg: Optional[dtime] = None
        has_plus = False

        m_plus = re.search(r"\+\s*(\d{2,4})", seg)
        if m_plus:
            tf_seg  = _parse_hhmm(m_plus.group(1))
            has_plus = True

        # Rango de horas global del segmento (sin estar pegado a un día)
        m_range = re.search(r"(?<![LMXJVSD\d])(\d{2,4})-(\d{2,4})\b", seg)
        if not has_plus and m_range:
            _tf = _parse_hhmm(m_range.group(1))
            _tu = _parse_hhmm(m_range.group(2))
            if _tf and _tu:
                tf_seg = _tf
                tu_seg = _tu

        # "HH A HH" o "HHMM A HHMM"
        if not has_plus and tf_seg is None:
            m_range_a = re.search(r"\b(\d{2,4})\s+A\s+(\d{2,4})\b", seg)
            if m_range_a:
                _tf = _parse_hhmm(m_range_a.group(1))
                _tu = _parse_hhmm(m_range_a.group(2))
                if _tf and _tu:
                    tf_seg = _tf
                    tu_seg = _tu

        # HASTA
        m_hasta = re.search(r"HASTA\s+(?:LAS\s+)?(\d{3,4})", seg)
        if m_hasta:
            tu_seg = _parse_hhmm(m_hasta.group(1))

        # COMPLETO
        if re.search(r"\bCOMPLETO\b", seg):
            tf_seg = None; tu_seg = None

        # 4 dígitos sueltos como hora única (sin +, sin rango)
        if tf_seg is None and tu_seg is None and not has_plus:
            bare_4 = re.findall(r"(?<![LMXJVSD])(?<![0-9])(1[6-9]\d{2}|2[0-2]\d{2})(?!\d)", seg)
            if bare_4:
                tf_seg = _parse_hhmm(bare_4[0])
                tu_seg = tf_seg  # exacto

        # Aplicar ventana a los días no cubiertos por patrones específicos
        has_global_time = tf_seg is not None or tu_seg is not None or has_plus
        for d in seg_days:
            if d not in handled_days_in_seg:
                if has_global_time:
                    _apply_window([d], tf_seg, tu_seg)
                else:
                    _apply_window([d], None, None)  # sin restricción horaria

    # Dividir en segmentos: por ; . \n y también por SAB/DOM (ya normalizados a S/D)
    segments = re.split(r"[;.\n]+", t_clean)
    for seg in segments:
        _parse_segment(seg.strip())

    # Días sin ventana de tiempo explícita → sin restricción
    # (ya procesados arriba con _apply_window([d], None, None))

    # ── Negaciones: "L NO"
    negated: set[int] = set()
    for nm in re.finditer(r"(?<![A-Z])([LMXJVSD])\s+NO\b", t):
        d_neg = DMAP.get(nm.group(1))
        if d_neg is not None:
            negated.add(d_neg)
    if negated:
        weekdays_set -= negated
        for d in negated:
            per_day_windows.pop(d, None)

    # ── Fallback global si no hay per_day_windows pero sí días
    available_from: Optional[dtime]  = None
    available_until: Optional[dtime] = None

    if per_day_windows:
        # Derivar from/until globales del conjunto de ventanas (para compatibilidad)
        all_froms  = [w["from"]  for w in per_day_windows.values() if w["from"]  is not None]
        all_untils = [w["until"] for w in per_day_windows.values() if w["until"] is not None]
        if all_froms:
            available_from  = min(all_froms)
        if all_untils:
            available_until = max(all_untils)
    else:
        # Sin per_day_windows: intentar parseo global simple
        m_plus = re.search(r"\+\s*(\d{2,4})", t)
        if m_plus:
            available_from = _parse_hhmm(m_plus.group(1))
        m_range = re.search(r"\b(\d{2,4})\s+A\s+(\d{2,4})\b", t)
        if m_range:
            tf = _parse_hhmm(m_range.group(1))
            tu = _parse_hhmm(m_range.group(2))
            if tf and available_from is None:
                available_from = tf
            if tu:
                available_until = tu
        m_hasta = re.search(r"HASTA\s+(?:LAS\s+)?(\d{3,4})", t)
        if m_hasta and available_until is None:
            available_until = _parse_hhmm(m_hasta.group(1))

    # ── Si no hay días detectados, es disponibilidad total
    if not weekdays_set:
        # Texto tiene hora pero no días → cualquier día laborable (L-V)
        if available_from or available_until or per_day_windows:
            weekdays_set = {0, 1, 2, 3, 4}  # L-V

    # ── Filtrar fines de semana (el ranking solo es L-V)
    weekdays_set = {d for d in weekdays_set if d <= 4}  # 0-4 = L-V
    for wk_d in (5, 6):
        per_day_windows.pop(wk_d, None)

    # ── PF override: asegurar que cada PF queda dentro de la ventana del día
    #    aunque el horario general lo excluyera.
    for _pf in preferred_slots:
        _pf_wd = _pf.get("weekday")
        _pf_t = _pf.get("time")
        if _pf_wd is None or _pf_t is None or _pf_wd not in range(5):
            continue
        weekdays_set.add(_pf_wd)
        win = per_day_windows.get(_pf_wd)
        if win is None:
            per_day_windows[_pf_wd] = {"from": _pf_t, "until": _pf_t}
        else:
            # Ampliar ventana para incluir TODAS las PF de ese día.
            wf = win.get("from")
            wu = win.get("until")
            if wf is None or _pf_t < wf:
                per_day_windows[_pf_wd]["from"] = _pf_t
            if wu is None or _pf_t > wu:
                per_day_windows[_pf_wd]["until"] = _pf_t

    # ── Inferir preferred si hay hora exacta única (sin PF explícita)
    if preferred_weekday is None and len(weekdays_set) == 1:
        d0 = next(iter(weekdays_set))
        w0 = per_day_windows.get(d0, {})
        if w0.get("from") is not None and w0.get("from") == w0.get("until"):
            preferred_weekday = d0
            preferred_time    = w0["from"]

    return {
        "weekdays":          sorted(weekdays_set),
        "available_from":    available_from,
        "available_until":   available_until,
        "per_day_windows":   per_day_windows,
        "preferred_weekday": preferred_weekday,
        "preferred_time":    preferred_time,
        "preferred_slots":   preferred_slots,
        "manual_only":       False,
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
            per_day_windows={},
            preferred_weekday=None,
            preferred_time=None,
            preferred_slots=[],
            manual_only=False,
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
