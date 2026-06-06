# context.md — Contexto acumulado del proyecto Voltreo

Historial de decisiones técnicas, cambios importantes y deuda conocida.
Actualizar cuando se hagan cambios significativos.

---

## Estado actual

- **Rama de producción:** `main` → Streamlit Cloud → `voltreo.streamlit.app`
- **Repo:** `JaviGonzalez5/Voltreo` (remote `origin`)
- `refactor-voltreo-v1` ya fusionado a `main` (cherry-pick) — puede borrarse

---

## Cambios recientes en `main`

### Email unificado (Resend)
- Antes: dos sistemas — `email_sender.py` (Resend) + `email_service.py` (SMTP, duplicado)
- Ahora: **un solo sistema**, `src/email_sender.py` vía Resend; `email_service.py` eliminado
- Funciones: `notify_result`, `notify_bracket_published`, `notify_registration_received`
- `notify_registration_received` filtra emails inválidos, devuelve `False` si Resend no configurado
- Config: `RESEND_API_KEY` (env var / secrets)

### Seguridad — vista pública
- `render_public_tournament()` hace `t.registrations = []` tras cargar
- Datos personales (emails, teléfonos, apellidos) no se exponen en `?t=<uuid>`

### Móvil desactivado
- Feature móvil quedó a medias (`src/mobile_app.py` ausente, `_is_mobile` sin definir) → crash `NameError`
- Fix: `_is_mobile = False`, nav móvil off (sus `st.button` se colaban en desktop ignorando CSS)

### UX dashboard / sidebar (FASE 1-5)
- Hero con eyebrow, KPIs con notas, onboarding por pasos
- "Mis Torneos" en sección Principal; pasos condicionales en sidebar de ranking
- Jerga → español llano ("club_admin" → "Admin de club")
- Excepciones de BD ya no se filtran al usuario

### Auditoría
- Tabla `audit_log` + `log_audit_event()` en `src/db.py`
- Eventos: login + fases (torneos pendiente)

---

## Tablas Supabase

| Tabla | `club_id` | Notas |
|---|---|---|
| `clubs` | raíz | — |
| `users` | ✅ | Admins (no jugadores) |
| `ranking_phases` | ✅ | JSONB separados |
| `tournaments` | ✅ | JSONB único `tournament_data` |
| `audit_log` | ✅ | Log de acciones |

`SUPABASE_KEY` = **service_role**. Nunca exponer.

---

## RLS — estado

- SQL listo + idempotente en `src/db_rls.sql` (5 tablas, 9 policies)
- ⚠️ **VERIFICAR si está ejecutado en Supabase.** ROADMAP lo marca hecho;
  confirmar en dashboard antes de fiarse. Policies: solo `service_role` accede.
- Aislamiento en app: `current_club_id()` + `.eq("club_id", ...)` en todas las queries

---

## Deuda técnica conocida

### Alta
| Problema | Archivo | Impacto |
|---|---|---|
| `app.py` ~7.600 líneas, 16 páginas en un archivo | `app.py` | Difícil de mantener |
| `AUTH_COOKIE_SECRET` usa `SUPABASE_KEY` como fallback | `src/auth.py` | Rotar DB key invalida sesiones |
| Confirmar RLS ejecutado en Supabase | `src/db_rls.sql` | Riesgo cross-club si falta |

### Media
| Problema | Impacto |
|---|---|
| ~377 usos de `st.session_state` con claves string dispersas | Bugs silenciosos |
| `delete_user` no valida club del objetivo | Bajo hoy, alto si se amplían permisos |
| Feature móvil a medias (desactivada, no borrada) | Código muerto |

### Baja
| Problema | Impacto |
|---|---|
| `syltek_connector.py` (1.557 líneas) acoplado al core | Playwright pesado, scraping frágil |
| Pydantic V2 `Field(env=...)` deprecado en `config.py` | Warning, romperá en Pydantic V3 |

---

## Próximas mejoras (ROADMAP)

1. **Filtros y búsqueda en listas** — `st.multiselect` por categoría/estado (QoL, P1, in-app)
2. Cablear notificaciones: resultado→rival, cuadro→participantes (funcs ya existen)
3. Móvil jugadores (Next.js — proyecto aparte, P2)
4. Rotar secrets, runbook operaciones, backup verificado (P3)

---

## Configuración de producción

```toml
SUPABASE_URL       = "https://xxxx.supabase.co"
SUPABASE_KEY       = "eyJ..."          # service_role (NO anon)
AUTH_COOKIE_SECRET = "..."             # PENDIENTE: clave independiente
RESEND_API_KEY     = "re_..."          # emails (opcional)
```

Remotes:
```
origin → https://github.com/JaviGonzalez5/Voltreo.git              (producción)
v2     → JaviGonzalez5/Ranking-Padelplus-Automatizado.git          (antiguo, no usar)
```

---

## Decisiones de arquitectura

| Decisión | Razón |
|---|---|
| Un solo `app.py` por ahora | Partir el monolito es trabajo grande, no sobre la marcha |
| Resend (no SMTP) | API moderna, una sola config, ya en requirements |
| `service_role` en backend | Streamlit server-side, nunca expuesto al navegador |
| UUID como secreto compartible | No-adivinable, sin auth extra |
| Pydantic v2 para modelos | Validación + serialización JSONB |
| JSONB único para torneo | Torneo es unidad coherente, evita joins |
| `club_id` en todas las queries | Multi-tenant, segunda capa sobre RLS |
| Móvil dedicado descartado | `st.button` no se oculta por CSS; rompía desktop |

---

## Checklist antes de tocar producción

- [ ] Tests pasan: `pytest -q` (205 actualmente)
- [ ] Compila: `python -m compileall app.py src`
- [ ] Sin refs a `email_service`: `grep -R email_service --include=*.py .`
- [ ] `SUPABASE_KEY` es `service_role` en Streamlit Cloud
- [ ] RLS confirmado ejecutado en Supabase
- [ ] `AUTH_COOKIE_SECRET` añadido en secrets
