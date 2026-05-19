"""
Conector con Syltek/Padelplus usando Playwright.

MODO SEGURO POR DEFECTO:
- Solo lectura hasta que se active explícitamente el modo escritura.
- Nunca crea reservas, envía emails ni modifica datos sin confirmación.
- Guarda capturas de debug en /debug/screenshots.
- Se detiene si detecta captcha o 2FA.

IMPORTANTE PARA PERSONALIZAR:
Los selectores CSS/XPath de Syltek son específicos de cada instalación.
Las funciones marcadas con  # <<SELECTOR PENDIENTE>> necesitan
que tú inspeccionnes el HTML de tu Syltek y pegues el selector correcto.
Usa el botón "Debug: Guardar HTML" en la UI para obtener el código fuente.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .config import settings
from .models import Booking, Court, Group, Pair, Player

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Excepción de seguridad
# ---------------------------------------------------------------------------

class SyltekSecurityStop(Exception):
    """Se lanza cuando se detecta un elemento que requiere intervención humana."""


class SyltekLoginError(Exception):
    """Se lanza cuando el login falla."""


# ---------------------------------------------------------------------------
# Conector principal
# ---------------------------------------------------------------------------

class SyltekConnector:
    """
    Abre un navegador Playwright y gestiona la sesión con Syltek.
    Uso recomendado como context manager async:

        async with SyltekConnector() as conn:
            groups = await conn.get_groups()
    """

    def __init__(
        self,
        url: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dry_run: bool = True,
        headless: bool = True,
    ):
        self.url = url or settings.syltek_url
        self.user = user or settings.syltek_user
        self._password = password or settings.syltek_password  # nunca loggeamos esto
        self.dry_run = dry_run
        self.headless = headless

        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False

        self._screenshots_dir = Path(settings.screenshots_dir)
        self._html_dir = Path(settings.html_dump_dir)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self):
        await self._launch()
        return self

    async def __aexit__(self, *args):
        await self._close()

    # ------------------------------------------------------------------
    # Inicialización
    # ------------------------------------------------------------------

    async def _launch(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright no está instalado. Ejecuta: pip install playwright && playwright install chromium"
            )

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900}
        )
        self._page = await self._context.new_page()
        logger.info("Navegador iniciado. dry_run=%s", self.dry_run)

    async def _close(self) -> None:
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw") and self._pw:
            await self._pw.stop()
        logger.info("Navegador cerrado.")

    # ------------------------------------------------------------------
    # Utilidades de debug
    # ------------------------------------------------------------------

    async def save_screenshot(self, name: str) -> Path:
        path = self._screenshots_dir / f"{name}_{datetime.now().strftime('%H%M%S')}.png"
        if self._page:
            await self._page.screenshot(path=str(path), full_page=True)
            logger.debug("Screenshot guardada: %s", path)
        return path

    async def save_html(self, name: str) -> Path:
        path = self._html_dir / f"{name}_{datetime.now().strftime('%H%M%S')}.html"
        if self._page:
            content = await self._page.content()
            path.write_text(content, encoding="utf-8")
            logger.debug("HTML guardado: %s", path)
        return path

    async def _check_for_captcha_or_2fa(self) -> None:
        """
        Intenta detectar captchas o 2FA. Si los encuentra, guarda screenshot
        y lanza SyltekSecurityStop para pedir intervención manual.
        """
        page_content = await self._page.content()
        captcha_keywords = ["captcha", "recaptcha", "hcaptcha", "challenge"]
        twofa_keywords = ["two-factor", "2fa", "autenticación en dos", "verificación"]

        lower = page_content.lower()
        for kw in captcha_keywords:
            if kw in lower:
                await self.save_screenshot("captcha_detected")
                raise SyltekSecurityStop(
                    f"Captcha detectado ({kw}). Intervención manual necesaria."
                )
        for kw in twofa_keywords:
            if kw in lower:
                await self.save_screenshot("2fa_detected")
                raise SyltekSecurityStop(
                    f"2FA detectado ({kw}). Intervención manual necesaria."
                )

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self) -> bool:
        """
        Hace login en Syltek. Devuelve True si tiene éxito.

        <<SELECTOR PENDIENTE>>:
        Inspecciona tu página de login de Syltek y ajusta los selectores de:
          - Campo usuario
          - Campo contraseña
          - Botón de submit
          - Elemento que indica login correcto (ej. nombre de usuario en header)
        """
        if not self.url:
            raise SyltekLoginError("SYLTEK_URL no configurada. Revisa tu .env")
        if not self.user or not self._password:
            raise SyltekLoginError("SYLTEK_USER o SYLTEK_PASSWORD no configurados.")

        logger.info("Navegando a %s ...", self.url)
        await self._page.goto(self.url, wait_until="networkidle")
        await self._check_for_captcha_or_2fa()
        await self.save_screenshot("login_page")

        # ------------------------------------------------------------------
        # AJUSTA ESTOS SELECTORES inspeccionando tu Syltek con DevTools (F12)
        # ------------------------------------------------------------------
        SELECTOR_USER = "input[name='username']"        # <<SELECTOR PENDIENTE>>
        SELECTOR_PASS = "input[name='password']"        # <<SELECTOR PENDIENTE>>
        SELECTOR_SUBMIT = "button[type='submit']"       # <<SELECTOR PENDIENTE>>
        SELECTOR_LOGIN_OK = ".user-name, .navbar-user"  # <<SELECTOR PENDIENTE>>
        # ------------------------------------------------------------------

        try:
            await self._page.fill(SELECTOR_USER, self.user)
            # Contraseña: no la loggeamos nunca
            await self._page.fill(SELECTOR_PASS, self._password)
            await self._page.click(SELECTOR_SUBMIT)
            await self._page.wait_for_load_state("networkidle")
            await self._check_for_captcha_or_2fa()
        except SyltekSecurityStop:
            raise
        except Exception as exc:
            await self.save_screenshot("login_error")
            raise SyltekLoginError(f"Error durante el login: {exc}") from exc

        # Verificar si el login fue exitoso
        try:
            await self._page.wait_for_selector(SELECTOR_LOGIN_OK, timeout=5000)
            self._logged_in = True
            logger.info("Login correcto para usuario: %s", self.user)
            await self.save_screenshot("login_success")
            return True
        except Exception:
            await self.save_screenshot("login_failed")
            page_title = await self._page.title()
            raise SyltekLoginError(
                f"Login fallido. Título de página: '{page_title}'. "
                f"Revisa las credenciales y los selectores en syltek_connector.py"
            )

    # ------------------------------------------------------------------
    # Lectura de datos (READ ONLY)
    # ------------------------------------------------------------------

    async def get_groups(self) -> list[Group]:
        """
        Lee los grupos del ranking desde Syltek.

        <<SELECTOR PENDIENTE>>:
        - Navega a la sección de ranking en Syltek.
        - Inspecciona la tabla/lista de grupos.
        - Ajusta la URL de navegación y los selectores.

        Por ahora devuelve lista vacía hasta configurar selectores reales.
        """
        self._assert_logged_in()
        logger.warning(
            "get_groups() no implementado aún. "
            "Configura los selectores en syltek_connector.py y carga datos manualmente."
        )
        await self.save_html("groups_page")
        return []

    async def get_bookings(self, from_date: date, to_date: date) -> list[Booking]:
        """
        Lee las reservas existentes en el rango de fechas.

        <<SELECTOR PENDIENTE>>:
        - Navega al calendario/agenda de reservas.
        - Filtra por fechas.
        - Parsea filas de la tabla de reservas.
        """
        self._assert_logged_in()
        logger.warning("get_bookings() no implementado aún. Devolviendo lista vacía.")
        await self.save_html("bookings_page")
        return []

    async def get_courts(self) -> list[Court]:
        """
        Lee las pistas disponibles.

        <<SELECTOR PENDIENTE>>:
        - Navega a la sección de pistas.
        - Parsea nombres e IDs.
        """
        self._assert_logged_in()
        logger.warning("get_courts() no implementado aún. Devolviendo lista vacía.")
        return []

    # ------------------------------------------------------------------
    # Escritura de datos (WRITE — bloqueado en dry_run)
    # ------------------------------------------------------------------

    async def create_booking(self, *args, **kwargs) -> None:
        """
        Crea una reserva real en Syltek.
        NUNCA se ejecuta en modo dry_run.
        Requiere confirmación explícita del usuario.

        <<SELECTOR PENDIENTE>>: implementar cuando los selectores estén claros.
        """
        self._assert_write_allowed()
        raise NotImplementedError(
            "create_booking() aún no implementado. "
            "Configura los selectores antes de activar escritura."
        )

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _assert_logged_in(self) -> None:
        if not self._logged_in:
            raise SyltekLoginError("No has iniciado sesión. Llama a login() primero.")

    def _assert_write_allowed(self) -> None:
        if self.dry_run:
            raise PermissionError(
                "Modo dry_run activo. Para escribir en Syltek desactiva dry_run "
                "y confirma explícitamente la acción."
            )


# ---------------------------------------------------------------------------
# Función de ayuda para ejecutar desde scripts síncronos
# ---------------------------------------------------------------------------

def run_login_check(url: str, user: str, password: str) -> tuple[bool, str]:
    """
    Comprueba el login de forma síncrona (para Streamlit).
    Devuelve (exito, mensaje).
    """
    async def _check():
        async with SyltekConnector(
            url=url, user=user, password=password, dry_run=True, headless=True
        ) as conn:
            await conn.login()
            return True, "Login correcto"

    try:
        return asyncio.run(_check())
    except SyltekSecurityStop as e:
        return False, f"Seguridad detectada: {e}"
    except SyltekLoginError as e:
        return False, f"Error de login: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"
