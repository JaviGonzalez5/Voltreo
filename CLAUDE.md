# Guía para Claude: Voltreo

## Objetivo del producto

Voltreo es una aplicación Streamlit profesional para gestionar rankings, torneos, pistas, horarios y exportaciones de clubes deportivos. Prioriza claridad operativa, navegación guiada y confianza visual para usuarios no técnicos.

## Reglas de trabajo

- Mantén el punto de entrada en `app.py` y evita crear un frontend paralelo si no se solicita expresamente.
- Haz cambios quirúrgicos: respeta el flujo por `st.session_state["_nav_page"]`, los módulos de `src/` y los nombres de páginas existentes.
- No mezcles mejoras visuales con cambios de lógica de negocio salvo que sea imprescindible.
- Ejecuta validación específica antes de entregar: `python -m py_compile app.py` y, si hay tiempo, `pytest tests/ -v`.

## Criterios móviles obligatorios

- Prueba siempre en viewport móvil aproximado `390x844` antes de cerrar una mejora visual.
- El botón de abrir/cerrar sidebar debe quedar visible y con área táctil mínima de `44px`.
- Los botones principales, descargas, formularios, tabs y expanders deben tener mínimo `44px` de alto.
- Evita zoom automático en iOS/Android usando `font-size: 16px` en inputs, selects y textareas.
- Cualquier tabla, calendario o DataFrame ancho debe tener scroll horizontal con `-webkit-overflow-scrolling: touch`.
- No permitas overflow horizontal de la página completa; el contenido debe caber en `100vw`.
- En móvil, las columnas de Streamlit deben poder apilarse y no forzar tarjetas estrechas.

## Estilo visual

- Usa el sistema existente: verde Voltreo `#00c853`, fondo claro `#f0f4f8`, sidebar oscuro `#07121f`.
- Conserva tarjetas blancas, radios de `12-18px`, sombras suaves y jerarquía tipográfica marcada.
- Evita emojis nuevos en exceso; ya existen como apoyo visual en navegación y estados.
- Mantén textos orientados a acción: “Configura”, “Importa”, “Genera”, “Exporta”.

## Checklist antes de entregar

- Home visible sin login y sin barra/chrome de Streamlit.
- Sidebar navegable desde móvil.
- Ranking y Torneos no muestran pasos bloqueados sin explicación.
- Formularios se leen sin pinchar/zoom.
- Calendario y tablas se desplazan horizontalmente sin romper el layout.
- No hay errores de sintaxis ni cambios no relacionados.
