"""
Marca de la plataforma (centralizada).

Cambiar el nombre comercial es modificar SOLO este archivo.
"""

import os

BRAND_NAME     = "Voltreo"
BRAND_MONOGRAM = "V"                      # letra del logo
BRAND_SUFFIX   = "Sports Manager"         # bajada bajo el nombre
BRAND_TAGLINE  = "La plataforma para gestionar torneos, rankings, pistas y horarios de tu club."
BRAND_HEADLINE = "Gestiona tu club como un profesional."
BRAND_SUBHEAD  = ("Rankings automáticos, torneos con cuadro eliminatorio, calendarios "
                  "sin solapamientos y exportación directa para tus jugadores.")
BRAND_PITCH    = "Pádel · Pickleball · Multideporte · Multi-club"
BRAND_BETA_MSG = "Acceso por invitación durante la beta. Escríbenos para unirte."
BRAND_CONTACT  = "hola@voltreo.app"      # email de contacto visible en la landing

# Colores de marca (degradado del logo)
BRAND_GRADIENT = "linear-gradient(135deg,#00c853 0%,#00897b 100%)"


def public_base_url() -> str:
    """URL base pública de la app (sin barra final).

    Override con la variable de entorno/secret ``VOLTREO_PUBLIC_URL`` cuando
    se use un dominio propio. Por defecto, el subdominio de Streamlit Cloud.
    """
    override = os.environ.get("VOLTREO_PUBLIC_URL", "").strip().rstrip("/")
    return override or f"https://{BRAND_NAME.lower()}.streamlit.app"
