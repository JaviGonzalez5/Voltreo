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
from __future__ import annotations

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

PADELPLUS_BASE = "https://padelplus.syltek.com"


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
        self.base = (url or settings.syltek_url or PADELPLUS_BASE).rstrip("/")
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

        login_candidates = [
            f"{self.base}/admin/login",
            f"{self.base}/login",
            f"{self.base}/users/login",
        ]

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
    group = Group(
        id=f"{ranking_id}_{group_name.replace(' ', '_')}",
        name=group_name,
    )

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        # Buscar la celda con nombre de equipo (típicamente tiene "Equipo" o es la 6ª columna)
        team_cell = None
        for cell in cells:
            text = cell.get_text(strip=True)
            # Los nombres de equipo suelen ser "Apellido1- Apellido2"
            if re.search(r"[A-ZÁÉÍÓÚ][a-záéíóú]+-\s*[A-ZÁÉÍÓÚ]", text):
                team_cell = cell
                break

        if not team_cell:
            continue

        team_name = team_cell.get_text(strip=True)
        # Dividir "García- Martínez" en dos jugadores
        parts = re.split(r"-\s*", team_name, maxsplit=1)
        if len(parts) == 2:
            p1 = Player(name=parts[0].strip())
            p2 = Player(name=parts[1].strip())
        else:
            p1 = Player(name=team_name)
            p2 = Player(name="")

        pair = Pair(
            name=team_name,
            player_1=p1,
            player_2=p2,
            group_id=group.id,
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
