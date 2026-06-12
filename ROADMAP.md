# Voltreo — Roadmap SaaS v1

> **Para orientarte rápido en una conversación nueva:** lee `CLAUDE.md` (estructura, stack, tablas, routing) + esta sección **Estado actual**. No hace falta leer `app.py` entero (8.800 líneas).

## Estado actual (act. 2026-06-12)

App **en producción** en `https://voltreo.streamlit.app` (deploy desde `main`). Tras cada `git push` hay que hacer **Reboot app** manual en Streamlit Cloud para ver los cambios.

**Qué funciona hoy (live):**
- Multi-club con aislamiento por `club_id` · roles `superadmin` / `club_admin`
- **Ranking** completo: fases, import CSV/Excel, calendario, resultados, clasificación, export Excel + mensajes WhatsApp, clasificación pública `?r=`
- **Torneos** completos: config, parejas/inscripción, cuadro, horarios, resultados + avance, export, vista pública `?t=` e inscripción `?join=`
- **ELO dual** (ranking vs torneos, históricos separados) — `src/elo_engine.py`, `src/db_elo.py`, página `players`. Requiere `src/db_elo.sql` ejecutado en Supabase
- **Portal público de jugadores** — self-signup + directorio de competición entre clubs (`src/player_portal.py`)
- **Tema oscuro** deportivo (base `#07111d`)
- Emails transaccionales vía Resend · audit log · rate limiting login · RLS activo

**URL pública centralizada:** `branding.public_base_url()` (override con secret `VOLTREO_PUBLIC_URL` para dominio propio). No hardcodear `streamlit.app`.

**Pulido UX hecho 2026-06-12** (8 fixes, todos compilan):
1. Contraste onboarding home (texto invisible sobre tarjeta oscura)
2. 2× `st.error` crudos → mensaje humano + detalle técnico en expander
3. Botón "Guardar" → "Guardar nombre" (renombrar fase)
4. Export Excel ya no filtra ruta del sistema; confirma nº grupos/partidos
5. Nombres de jugador duplicados ya no colisionan en selector de perfil (selectbox por `id` + `format_func`)
6. Medallas 🥇🥈🥉 solo a jugadores con partidos (0 PJ → "–")
7. Error de listado de jugadores ya no cita `db_elo.sql` al gestor
8. URLs públicas centralizadas en `public_base_url()` (11 sitios)

**Próximo candidato de trabajo:** seguir auditoría UX/UI por páginas (pendientes: `club_config`, `t_config`, `results`). Usar skill `voltreo-ux-ui-polisher`.

---

## Evaluación arquitectural honesta

### Qué hace bien Streamlit (mantener)
- Panel de administración para superadmin (CRUD clubs, usuarios, fases)
- Configuración de ranking y torneos (formularios complejos, poca concurrencia)
- Exportación Excel / mensajes WhatsApp
- Generación y planificación de calendarios (algoritmo existente)

### Limitaciones BLOQUEANTES para producto vendible

| Limitación | Impacto | Solución |
|-----------|---------|----------|
| Sin URL routing real | No se pueden compartir cuadros/rankings por enlace | Añadir capa Next.js pública |
| Sidebar 306px fija en móvil | App inutilizable en teléfono para jugadores | Next.js mobile-first para vistas de jugador |
| Sin rate limiting nativo | Brute force en login posible | ✅ Implementado (process-level por username, 5 intentos / 5 min) |
| Sin tiempo real | No se pueden ver resultados en vivo | Supabase Realtime en Next.js (futuro) |
| Max ~12 usuarios concurrentes | No escala para torneos grandes con muchos admins | Aceptable para v1 (1 admin/club) |

### Decisión arquitectural
```
Streamlit (admin privado)  ←→  Supabase (DB)  ←→  Next.js (vistas públicas)
```

---

## Fases del roadmap

---

## FASE P0 — Fundación estable (Semanas 1-2)
**Objetivo: que lo que existe funcione sin fallos y sea seguro.**

### ✅ Completado en este sprint

| Item | Estado | Evidencia |
|------|--------|-----------|
| Rate limiting en login (5 intentos / 5 min lockout) | ✅ | test_auth_security.py |
| Rate limiting mejorado a process-level con threading.Lock | ✅ | Persiste entre pestañas/reruns del mismo proceso |
| Validación de contraseña robusta (8 chars, mayúscula, número) | ✅ | test_auth_security.py |
| `create_user` valida rol en capa de datos | ✅ | `_VALID_ROLES` en db.py |
| `upsert_phase` deactiva siblings en UPDATE también | ✅ | test: múltiples fases activas |
| `set_phase_active` sin race condition | ✅ | Reordenado |
| Stale schedule_result limpiado al reimportar grupos | ✅ | app.py línea ~1994 |
| Torneos persistidos a Supabase (t_config + t_schedule) | ✅ | `upsert_tournament` llamado |
| Time parse crash en editor de partidos | ✅ | try/except IndexError, ValueError |
| `groups_qualifiers=0` y `bracket n=0` no crashean | ✅ | 19 tests passing |
| Health-check `?health=1` corregido (doble `set_page_config`) | ✅ | `_early_health` antes de `st.set_page_config` |
| Excepciones silenciadas en carga de datos → `logging.exception` | ✅ | Fase y torneo muestran warning genérico al usuario |
| Confirmación de inscripción por email (Resend) | ✅ | `src/email_sender.py` + tests |
| Vista pública de torneo compartible por URL | ✅ | `src/public_view.py` → `?t=<id>` |
| Vista pública de ranking compartible por URL | ✅ | `src/public_ranking.py` → `?r=<id>` |
| Inscripción pública en torneo por URL | ✅ | `src/public_view.py` → `?join=<id>` |
| Test suite: 233 tests | ✅ | 233/233 PASSED |
| RLS en Supabase (5 tablas, 9 policies) | ✅ | Ejecutado manualmente en Supabase |
| Audit log: tabla + helper `log_audit_event` | ✅ | login\_blocked/failed/success + create/update\_phase |

### ✅ Ejecutado manualmente en Supabase

- `ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_active` — ejecutado
- `src/db_rls.sql` completo ejecutado — RLS activo en 5 tablas, 9 policies, `audit_log` creado

---

## FASE P1 — Funcionalidad completa de Ranking (Semanas 2-4)
**Objetivo: que un club pueda gestionar una temporada entera desde la app.**

### Módulo Ranking — estado real

| Feature | Estado actual | Notas |
|---------|--------------|-------|
| Crear temporadas/fases | ✅ Funciona | — |
| Importar jugadores/parejas CSV | ✅ Funciona | — |
| Generar calendario | ✅ Funciona | — |
| Registrar resultados de partido | ✅ Funciona | `page == "results"` con data_editor, sets + WO |
| Clasificación automática | ✅ Funciona | `page == "standings"` + `src/ranking_scorer.py` |
| Reglas de puntuación configurables | ✅ Funciona | UI en `page == "config"` (pts victoria/empate/derrota/bonus) |
| Exportar Excel con hoja de clasificación | ✅ Funciona | `src/excel_exporter.py` hoja "Clasificación" |
| Clasificación pública compartible por URL | ✅ Funciona | `?r=<phase_id>` via `src/public_ranking.py` |
| Historial y trazabilidad (audit log) | ✅ Parcial | Tabla + 5 eventos (login + fases); torneos y más pendiente |

---

## FASE P1 — Funcionalidad completa de Torneos (Semanas 2-4)

### Módulo Torneos — estado real

| Feature | Estado actual | Notas |
|---------|--------------|-------|
| Crear torneo con formato | ✅ Funciona | `page == "t_config"` |
| Gestión de parejas e inscripciones | ✅ Funciona | `page == "t_pairs"` |
| Generar grupos y cuadro | ✅ Funciona | `page == "t_generate"` |
| Asignar horarios/pistas | ✅ Funciona | `page == "t_schedule"` |
| Registrar resultados partido a partido | ✅ Funciona | `page == "t_results"` con selector de ganador |
| Avance automático del cuadro | ✅ Funciona | `src/tournament_results.py` → `_propagate()` |
| Vista pública compartible | ✅ Funciona | `src/public_view.py` → `?t=<id>` |
| Inscripción pública por URL | ✅ Funciona | `src/public_view.py` → `?join=<id>` |
| Exportar Excel | ✅ Funciona | `page == "t_export"` |
| Filtros y búsqueda en listas | ✅ Funciona | `src/list_filters.py` + UI en Mis Rankings, Mis Torneos, Admin Clubs/Usuarios (texto + estado/categoría/rol/club) |

---

## FASE P2 — Experiencia de producto (Semanas 4-6)
**Objetivo: UX premium, móvil, funcionalidades de valor diferencial.**

### Vistas públicas básicas — ✅ ya existen en Streamlit

Las vistas públicas compartibles por enlace **ya están implementadas en la propia app Streamlit** (no requieren Next.js):
- `?r=<phase_id>`  → clasificación pública del ranking (`src/public_ranking.py`)
- `?t=<tournament_id>` → cuadro/resultados del torneo, shareable (`src/public_view.py`)
- `?join=<tournament_id>` → inscripción pública del jugador (`src/public_view.py`)

### Next.js layer — futuro móvil/premium para jugadores (no bloqueante)

Capa **opcional y futura**, orientada a una experiencia móvil-first y premium para jugadores (no para reemplazar las vistas públicas actuales, que ya funcionan):

```
/club/[slug]/ranking          → Clasificación pública (versión móvil premium)
/club/[slug]/torneo/[id]      → Cuadro/resultados (versión móvil premium)
/club/[slug]/partido/[id]     → Formulario de resultado para jugadores (móvil)
```

**Stack:** Next.js 14 (App Router) + Supabase JS client + Tailwind CSS  
**Hosting:** Vercel free tier  
**Tiempo estimado:** 2 semanas para las 3 rutas básicas

### Notificaciones (email básico)
- ✅ Confirmación de inscripción implementada en `src/email_sender.py` (Resend)
- Resultado registrado → notificar pareja rival (función `notify_result` lista, falta cablear)
- Cuadro publicado → notificar participantes (función `notify_bracket_published` lista, falta cablear)
- **Stack actual:** Resend vía `RESEND_API_KEY` (sistema único; `email_service.py`/SMTP eliminado)

---

## FASE P3 — Go-live y escala (Semanas 6-8)

### Seguridad adicional
- [x] RLS ejecutado en Supabase (5 tablas, 9 policies) — completado en P0
- [ ] Supabase Auth para jugadores (login social/magic link)
- [ ] Cloudflare en frente de Streamlit (rate limit por IP)
- [ ] Rotate service_role key cada 90 días

### Infraestructura
- [ ] Streamlit Community Cloud → Streamlit Private (si >10 clubs)
- [ ] Supabase Pro plan (si >500MB DB o >500k requests/mes)
- [ ] Backup automático Supabase (incluido en Pro)

### Testing pre-go-live
- [ ] E2E manual: login → crear club → configurar ranking → registrar resultado → verificar clasificación
- [ ] E2E manual: crear torneo → generar cuadro → registrar resultados → ver bracket en URL pública
- [ ] Test de aislamiento: Club A no puede ver datos de Club B (verificar en Supabase logs)
- [ ] Test de concurrencia: 5 pestañas simultáneas, cada una con distinto club
- [ ] Load test: 10 usuarios concurrentes durante 5 minutos

---

## Checklist de go-live

### Seguridad mínima ✅/❌
- [x] Rate limiting login implementado
- [x] Contraseñas robustas (8 chars, mayúscula, número)
- [x] Roles validados en capa de datos
- [x] RLS activado en Supabase — 5 tablas, 9 policies
- [x] Audit log operativo — `audit_log` en BD + `log_audit_event()` en `src/db.py`
- [ ] Secrets rotados (no usar contraseña de ejemplo)

### Funcionalidad mínima vendible
- [x] Multitenancy real (club_id en todas las operaciones)
- [x] Torneos persistidos a DB
- [x] Fases de ranking persistidas a DB
- [x] Registro de resultados de ranking
- [x] Clasificación automática
- [x] Registro de resultados de torneo + avance de cuadro
- [x] URL pública de torneo compartible (`src/public_view.py`)

### UX mínima
- [x] Login con mensajes de error claros
- [x] Onboarding para superadmin sin clubs
- [ ] Versión móvil para jugadores (Next.js)
- [ ] Tiempo de aprendizaje < 10 min (video demo)

### Operación
- [x] 233 tests automatizados
- [ ] Runbook de operaciones (cómo crear club, resetear contraseña, recuperar datos)
- [ ] Política de backup verificada
- [ ] Monitorización básica (Supabase logs activados)

---

## Riesgos abiertos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Streamlit Cloud down | Media | Alto | Migrar a servidor propio (Railway/Render) cuando haya 3+ clubs pagando |
| Supabase free tier límites (500MB, 2GB egress) | Media | Medio | Upgrade a Pro (~$25/mes) cuando se supere 50% del límite |
| Pérdida de sesión en Streamlit (timeout 30min) | Alta | Medio | Mostrar aviso "sesión expirando" + guardar en DB en cada paso |
| Contención de Playwright en Streamlit | Alta | Bajo | Mover Syltek connector a worker externo (Railway) en P2 |
| Escalabilidad con >20 clubs simultáneos | Baja ahora | Alto | Arquitectura Next.js + API FastAPI resuelve este riesgo |
| Brecha de datos entre clubs | Baja | Crítico | RLS activo en Supabase (5 tablas, 9 policies) + tests de aislamiento regulares |

---

## Estimación total

| Fase | Semanas | Coste estimado (dev solo) |
|------|---------|--------------------------|
| P0 (hecho) | 1 | ✅ Completado |
| P1 Ranking (resultados + clasificación) | 1.5 | ✅ Completado |
| P1 Torneos (resultados + avance cuadro) | 1.5 | ✅ Completado |
| P2 Next.js vistas públicas | 2 | 2 semanas |
| P2 Notificaciones email | 0.5 | 3 días |
| P3 Go-live + tests + documentación | 1 | 5 días |
| **TOTAL** | **7.5 semanas** | **~36 días de trabajo** |
