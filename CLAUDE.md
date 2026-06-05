# CLAUDE.md — Voltreo

Guía de referencia rápida para Claude Code. Léela antes de tocar cualquier archivo.

---

## ¿Qué es este proyecto?

**Voltreo** es un SaaS multi-club para gestión de clubs de pádel y pickleball.  
Construido con **Streamlit + Supabase + Pydantic v2**.  
Desplegado en **Streamlit Cloud** desde la rama `main` del repositorio `JaviGonzalez5/Voltreo`.

Funcionalidades principales:
- Rankings automáticos por fases (grupos round-robin, cuadro eliminatorio)
- Torneos multi-categoría con inscripción pública
- Planificación de horarios con restricciones de pistas y jugadores
- Exportación a Excel con plantillas del club
- Notificaciones por email (Resend)
- Multi-club con aislamiento total por `club_id`
- Roles: `superadmin` / `club_admin`

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Frontend / UI | Streamlit ≥ 1.39 |
| Base de datos | Supabase (PostgreSQL) |
| Modelos de datos | Pydantic v2 |
| Auth | bcrypt + cookies firmadas con HMAC-SHA256 |
| Email | Resend API (`RESEND_API_KEY`) |
| Scraping Syltek | Playwright + BeautifulSoup4 |
| Tests | pytest |
| Python | 3.12 |

---

## Estructura de archivos

```
app.py                         # Entrada única — 7.600 líneas, 16 páginas (monolito)
src/
  auth.py                      # Login, bcrypt, cookies de sesión, roles
  branding.py                  # Nombre, colores, textos de la marca (BRAND_NAME = "Voltreo")
  config.py                    # Configuración global (pydantic-settings)
  db.py                        # Capa de acceso a Supabase (SupabaseDB class)
  db_converters.py             # Serialización/deserialización Pydantic ↔ JSONB
  db_rls.sql                   # SQL para activar RLS (PENDIENTE de ejecutar)
  email_sender.py              # Emails transaccionales vía Resend (único sistema)
  excel_exporter.py            # Export Excel básico
  excel_template_exporter.py   # Export Excel con plantilla del club
  message_generator.py         # Mensajes de resultados (WhatsApp/texto)
  models.py                    # Modelos Pydantic del ranking (Player, Group, Match…)
  public_ranking.py            # Vista pública de ranking (?r=<uuid>)
  public_view.py               # Vista pública de torneo (?t=) e inscripción (?join=)
  ranking_generator.py         # Generación de grupos y calendario de ranking
  ranking_scorer.py            # Cálculo de puntuaciones y clasificación
  schedule_validator.py        # Validación de horarios (conflictos, solapamientos)
  scheduler.py                 # Planificador de horarios de ranking
  syltek_connector.py          # Conector con Syltek (reservas externas)
  tournament_generator.py      # Generación de grupos/cuadro de torneo
  tournament_models.py         # Modelos Pydantic del torneo (TournamentConfig…)
  tournament_results.py        # Resultados y campeones del torneo
  tournament_scheduler.py      # Planificador de horarios de torneo
  validators.py                # Validaciones de formulario
tests/
  test_*.py                    # 17 archivos de tests (pytest)
```

---

## Tablas Supabase

| Tabla | `club_id` | Propósito |
|---|---|---|
| `clubs` | es la raíz | Clubs registrados |
| `users` | ✅ | Usuarios admin (no jugadores) |
| `ranking_phases` | ✅ | Fases/temporadas del ranking |
| `tournaments` | ✅ | Torneos completos (JSONB) |
| `audit_log` | ✅ | Log de acciones (pendiente de crear) |

**Clave importante:** la app usa `SUPABASE_KEY` = **service_role key**.  
Nunca exponerla en código ni en repos públicos.

---

## Navegación / routing

La app usa un único `app.py` con routing por `st.session_state["_nav_page"]`.  
Las páginas son bloques `elif page == "nombre":`.

| Clave | Página |
|---|---|
| `home` | Dashboard principal |
| `club_config` | Configuración del club |
| `config` | Configuración del ranking |
| `import` | Importar jugadores/parejas |
| `generate` | Generar calendario de ranking |
| `results` | Registrar resultados |
| `standings` | Clasificación |
| `export` | Exportar Excel |
| `review` | Revisión de horarios |
| `syltek` | Conector Syltek |
| `t_config` | Configuración del torneo (paso 1) |
| `t_pairs` | Parejas e inscripciones (paso 2) |
| `t_generate` | Generar estructura (paso 3) |
| `t_schedule` | Horarios (paso 4) |
| `t_results` | Resultados del torneo (paso 5) |
| `t_export` | Exportar torneo (paso 6) |
| `admin` | Administración superadmin |

---

## URLs públicas (sin login)

| URL param | Vista | Función en public_view.py |
|---|---|---|
| `?t=<uuid>` | Resultados del torneo | `render_public_tournament()` |
| `?join=<uuid>` | Inscripción en torneo | `render_public_registration()` |
| `?r=<uuid>` | Ranking público | en `public_ranking.py` |

⚠️ Estas rutas usan `service_role` para escribir/leer. No requieren autenticación.

---

## Sistema de email

**Un único sistema: Resend** (`src/email_sender.py`).

| Función | Uso |
|---|---|
| `notify_result()` | Resultado de partido de ranking |
| `notify_bracket_published()` | Cuadro de torneo publicado |
| `notify_registration_received()` | Confirmación de inscripción |

Configurar en Streamlit Cloud secrets:
```toml
RESEND_API_KEY = "re_xxxxxxxxxxxx"
EMAIL_FROM     = "Voltreo <noreply@voltreo.app>"   # opcional
```
Si `RESEND_API_KEY` no está configurado, todas las funciones devuelven `False` silenciosamente.

---

## Roles y permisos

| Rol | Acceso |
|---|---|
| `superadmin` | Todos los clubs, gestión de usuarios y clubs |
| `club_admin` | Solo su propio club (`club_id` del usuario) |

El aislamiento se aplica en **dos capas**:
1. **App**: `current_club_id()` en `auth.py` devuelve el club del usuario
2. **DB**: todas las queries en `db.py` filtran por `club_id`

RLS está escrito en `src/db_rls.sql` pero **pendiente de ejecutar** en Supabase.

---

## Comandos útiles

```bash
# Ejecutar la app localmente
streamlit run app.py

# Tests
pytest tests/ -v

# Compilar todos los módulos (detección de errores de sintaxis)
python -m compileall app.py src

# Ver qué hay en la rama de refactor
git log --oneline refactor-voltreo-v1

# Subir cambios a producción
git push origin main   # ← despliega en Streamlit Cloud
```

---

## Secrets necesarios (Streamlit Cloud)

```toml
SUPABASE_URL          = "https://xxxx.supabase.co"
SUPABASE_KEY          = "eyJ..."          # service_role key
AUTH_COOKIE_SECRET    = "..."             # clave independiente para firmar sesiones
RESEND_API_KEY        = "re_..."          # opcional, para emails
EMAIL_FROM            = "..."             # opcional
```

---

## Convenciones de código

- Los modelos de datos usan **Pydantic v2** (`model_validate`, `model_dump`)
- La serialización a/de Supabase pasa por `src/db_converters.py`
- Los datos del torneo se guardan como un **JSONB único** en `tournament_data`
- Los datos del ranking se guardan como **JSONB separados** (`phase_config`, `groups_data`, etc.)
- No hay ORM — las queries son directas con `supabase-py`
- El estado de la UI vive en `st.session_state` (377 usos — deuda técnica conocida)

---

## Ramas Git

| Rama | Propósito |
|---|---|
| `main` | Producción (Streamlit Cloud lo despliega automáticamente) |
| `refactor-voltreo-v1` | Refactor en curso (no mergear a main sin revisión) |

Remote principal: `origin` → `https://github.com/JaviGonzalez5/Voltreo.git`
