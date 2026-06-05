# context.md — Contexto acumulado del proyecto Voltreo

Historial de decisiones técnicas, cambios importantes y deuda conocida.  
Actualizar cuando se hagan cambios significativos.

---

## Estado actual del proyecto

- **Rama de trabajo activa:** `refactor-voltreo-v1`
- **Producción:** rama `main` → Streamlit Cloud → `voltreo.streamlit.app`
- **Último commit de producción:** `6a079e5` (Add automatic registration confirmation email)
- **Último commit del refactor:** `51c16a9` (security: strip registrations from public tournament view)

---

## Refactor en curso — `refactor-voltreo-v1`

### Commits de esta rama (sobre `main`)

| Commit | Descripción |
|---|---|
| `470eef5` | Limpiar `__pycache__` del tracking de git, añadir `audit_artifacts/` al `.gitignore` |
| `3293347` | Unificar sistema de email — borrar `email_service.py`, extender `email_sender.py` con Resend |
| `51c16a9` | Seguridad: eliminar inscripciones (datos personales) de la vista pública de resultados |

### Tareas pendientes del refactor (priorizadas)

1. ✅ **Unificar email** — hecho en commit `3293347`
2. ✅ **Sanitizar datos públicos** — hecho en commit `51c16a9`
3. 🔲 **Activar RLS en Supabase** — SQL listo en `src/db_rls.sql`, pendiente de ejecutar
4. 🔲 **Añadir `AUTH_COOKIE_SECRET` en Streamlit Cloud secrets** — desacoplar de `SUPABASE_KEY`
5. 🔲 **Partir `app.py` en módulos de página** (`src/pages/`) — mayor impacto en mantenibilidad
6. 🔲 **Registro de resultados de partido** — gap funcional bloqueante para vender el ranking
7. 🔲 **Centralizar claves de session_state** en `src/state.py`
8. 🔲 **Hacer Syltek un módulo opcional** — quitar `playwright` del core

---

## Historial de cambios importantes (antes del refactor)

### Sistema de email
- Existía `src/email_sender.py` (Resend) para rankings/torneos
- Se creó `src/email_service.py` (SMTP) para inscripciones — **duplicado**
- **Decisión:** eliminar `email_service.py`, portar la función de inscripción a `email_sender.py`
- `send_registration_confirmation` → renombrada `notify_registration_received` (API consistente)

### Inscripción pública en torneos
- Flujo en 2 pasos: paso 1 = grid de categorías, paso 2 = formulario
- Botón "Acceder" en cada categoría (no "Inscribirse") para permitir ver inscritos aunque esté llena
- Pestaña "Parejas Inscritas" muestra nombre de pareja + nombre completo de cada jugador
- Formulario recoge: Nombre, Primer apellido, Segundo apellido, Teléfono, Email (todo obligatorio)
- Nombre de pareja generado automáticamente: `"J. García – C. López"`
- Disponibilidad por días: selector "Puedo / No puedo" + horario Desde/Hasta por día de la semana
- Los horarios Desde/Hasta se leen de la configuración del torneo (semana vs fin de semana)

### Modelos de datos del torneo
- `TournamentRegistration` tiene campos separados: `player1_surname1`, `player1_surname2`, etc.
- `pair_name` se genera automáticamente, el jugador no lo introduce
- `availability_windows: dict` almacena ventanas horarias por fecha ISO
- `unavailable_dates: list[str]` almacena fechas ISO en que no puede jugar

### Scheduler de torneo (pádel multi-día)
- `schedule_distribute_over_days: bool` — distribuye partidos entre todos los días del torneo
- `_player_day_busy` — restricción de máximo 1 partido por pareja por día
- `_day_hours(d)` — helper que devuelve horario correcto según día de semana (L-V vs S-D)
- `weekend_start_time / weekend_end_time` — franjas horarias de fin de semana en `TournamentConfig`

### Configuración de horarios
- Un torneo puede tener franjas distintas L-V y S-D
- Se detecta automáticamente si el rango de fechas incluye fin de semana
- En la vista de inscripción, los selectores de hora se limitan al rango configurado

### Bandeja de inscripciones (admin)
- Pestaña "📩 Inscripciones (N)" en `t_pairs` con recarga automática desde BD
- Organizada por categoría
- Subpestañas: Pendientes (con aprobar/rechazar) / Aprobadas / Rechazadas
- Al aprobar: se crea `TournamentPair` y se añade a `t.pairs`, estado → `APPROVED`

### Vista pública de torneos
- Fondo claro (`#f4f6f9`), hero verde, cards de categorías
- `t.registrations = []` en `render_public_tournament()` — los datos personales no se exponen en la vista de resultados

---

## Deuda técnica conocida

### Alta prioridad

| Problema | Archivo | Impacto |
|---|---|---|
| `app.py` tiene 7.630 líneas y 16 páginas | `app.py` | Muy difícil de mantener |
| Sin RLS activo en Supabase | `src/db_rls.sql` | Riesgo de cross-club si hay bug en `club_id` |
| `AUTH_COOKIE_SECRET` usa `SUPABASE_KEY` como fallback | `src/auth.py:116` | Rotación de DB key invalida sesiones |

### Media prioridad

| Problema | Impacto |
|---|---|
| 377 usos de `st.session_state` con claves string dispersas | Bugs silenciosos difíciles de rastrear |
| `delete_user` no valida que el usuario pertenezca al club del admin | Bajo riesgo hoy, alto si se amplían permisos |
| Sin registro de resultados de partido | Ranking no vendible sin esto |

### Baja prioridad

| Problema | Impacto |
|---|---|
| `syltek_connector.py` (1.557 líneas) acoplado al core | Playwright en requirements, scraping frágil |
| `get_tournament_public` devuelve `tournament_data` completo | Ya mitigado en la vista de resultados |

---

## Configuración de producción

### Streamlit Cloud secrets (mínimo necesario)

```toml
SUPABASE_URL       = "https://xxxx.supabase.co"
SUPABASE_KEY       = "eyJ..."          # service_role (NO anon key)
AUTH_COOKIE_SECRET = "..."             # PENDIENTE: añadir clave independiente
RESEND_API_KEY     = "re_..."          # para emails (opcional)
```

### Remotes Git

```
origin  → https://github.com/JaviGonzalez5/Voltreo.git        (producción)
v2      → https://github.com/JaviGonzalez5/Ranking-Padelplus-Automatizado.git  (antiguo, no usar)
```

---

## Decisiones de arquitectura tomadas

| Decisión | Razón |
|---|---|
| Un solo `app.py` por ahora | Partir el monolito es tarea del refactor, no cambiar sobre la marcha |
| Resend para email (no SMTP) | API moderna, una sola configuración, ya en `requirements.txt` |
| `service_role` en el backend | Streamlit es server-side, nunca expuesto al navegador |
| UUID como "secreto compartible" para vistas públicas | No-adivinable, sin auth extra necesaria |
| Pydantic v2 para todos los modelos | Validación automática, serialización a JSON para JSONB |
| JSONB único para torneo completo | Evita joins complejos, torneo es una unidad coherente |
| `club_id` en todas las queries | Aislamiento multi-tenant sin RLS (segunda capa de seguridad) |

---

## Checklist antes de hacer merge a main

- [ ] Tests pasan: `pytest tests/ -v`
- [ ] Sin errores de compilación: `python -m compileall app.py src`
- [ ] Sin referencias a `email_service`: `grep -R "email_service" . --include="*.py"`
- [ ] Confirmar que `SUPABASE_KEY` es `service_role` en Streamlit Cloud
- [ ] RLS ejecutado en Supabase (o decisión explícita de posponerlo)
- [ ] `AUTH_COOKIE_SECRET` añadido en secrets
