# 🎾 Voltreo

**Software de gestión de rankings y torneos para clubes de pádel y pickleball.**

---

## Para qué sirve

Organizar a mano los rankings y torneos de un club es lento y propenso a errores: emparejar grupos, cuadrar horarios sin que dos parejas coincidan ni se solapen las pistas, y recalcular clasificaciones cada jornada consume horas. Voltreo automatiza todo ese trabajo: genera los enfrentamientos, asigna los horarios respetando la disponibilidad de pistas y jugadores, y mantiene la clasificación al día sola. Además comunica los resultados, los cuadros y las inscripciones a los jugadores por email y permite descargar todo en Excel listo para imprimir o publicar.

---

## Características principales

- **Rankings por fases** — grupos round-robin con clasificación automática por puntos configurables (victoria / empate / derrota, bonus opcional) y desempates encadenados (diferencia de sets, diferencia de juegos, victorias, head-to-head). Soporta walkover/retirada.
- **Torneos con cuadro eliminatorio** — fase de grupos + cuadro (final, semifinales, cuadros de 4/8/16), partido de 3er/4º puesto opcional y soporte multi-categoría/división.
- **Inscripción pública de torneos** — los jugadores se inscriben desde un enlace público, sin necesidad de cuenta.
- **Generación de horarios sin conflictos** — asigna pistas y franjas respetando disponibilidad de pistas y parejas, evita solapamientos, fuerza separación mínima de días entre partidos de la misma pareja y reparte días/horas/pistas de forma equilibrada. Incluye un validador que detecta conflictos y solapamientos.
- **Exportación a Excel** — export básico y export con la plantilla del club (calendario por grupos, listado, auditoría de disponibilidad, pistas fijas, resumen de grupos y más).
- **Emails a jugadores (Resend)** — notificación de resultado de partido, aviso de cuadro publicado y confirmación de inscripción.
- **Vistas públicas sin login** — ranking público, resultados de torneo en directo y formulario de inscripción, cada uno con su enlace propio.
- **Multi-club con aislamiento total** — cada club ve únicamente sus datos (aislamiento por `club_id`). Roles `superadmin` (todos los clubes) y `club_admin` (su club).
- **Conector Syltek/Padelplus (opcional)** — lee rankings, grupos y reservas existentes para tenerlas en cuenta al cuadrar horarios.

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Frontend / UI | Streamlit |
| Base de datos | Supabase (PostgreSQL) |
| Modelos de datos | Pydantic v2 |
| Autenticación | bcrypt + cookies firmadas (HMAC-SHA256) |
| Email | Resend |
| Lenguaje | Python 3.12 |

---

## Despliegue

Voltreo se despliega en **Railway** (configurado vía `Procfile` y `railway.toml`, builder `nixpacks`) con **Supabase** como base de datos PostgreSQL.

Variables de entorno necesarias:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `SUPABASE_URL` | ✅ | URL del proyecto Supabase |
| `SUPABASE_KEY` | ✅ | **service_role key** de Supabase — secreto, nunca exponer |
| `AUTH_COOKIE_SECRET` | ✅ | Clave para firmar las cookies de sesión |
| `RESEND_API_KEY` | ❌ | API key de Resend. Sin ella, los emails se desactivan silenciosamente |
| `EMAIL_FROM` | ❌ | Remitente de los emails (ej. `Voltreo <noreply@voltreo.app>`) |
| `SYLTEK_USER` / `SYLTEK_PASSWORD` | ❌ | Credenciales del conector Syltek/Padelplus, si se usa |

Pasos:

1. Crear el proyecto en Supabase y aplicar el esquema (`src/db_schema.sql`) y las políticas RLS (`src/db_rls.sql`).
2. Conectar el repositorio a Railway.
3. Definir las variables de entorno anteriores en Railway.
4. Railway despliega automáticamente con cada push a la rama `main`.

---

## Licencia

Uso interno del club. No redistribuir.
