# PadelPlus — Roadmap SaaS v1

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
| Confirmación de inscripción por email (SMTP) | ✅ | `src/email_service.py` + tests |
| Vista pública de torneo compartible por URL | ✅ | `src/public_view.py` → `?t=<id>` |
| Vista pública de ranking compartible por URL | ✅ | `src/public_ranking.py` → `?r=<id>` |
| Inscripción pública en torneo por URL | ✅ | `src/public_view.py` → `?join=<id>` |
| Test suite: 204 tests | ✅ | 204/204 PASSED |
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

### Next.js layer (vistas públicas y móvil)

```
/club/[slug]/ranking          → Clasificación pública del ranking
/club/[slug]/torneo/[id]      → Cuadro/resultados del torneo (shareable)
/club/[slug]/partido/[id]     → Formulario de resultado para jugadores (móvil)
```

**Stack:** Next.js 14 (App Router) + Supabase JS client + Tailwind CSS  
**Hosting:** Vercel free tier  
**Tiempo estimado:** 2 semanas para las 3 rutas básicas

### Notificaciones (email básico)
- ✅ `send_registration_confirmation` implementado en `src/email_service.py` (SMTP con TLS)
- Resultado registrado → notificar pareja rival (pendiente)
- Cuadro publicado → notificar participantes (pendiente)
- **Stack actual:** SMTP configurable vía `st.secrets["email"]`

---

## FASE P3 — Go-live y escala (Semanas 6-8)

### Seguridad adicional
- [ ] Ejecutar `src/db_rls.sql` en Supabase (RLS real)
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
- [x] 204 tests automatizados
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
