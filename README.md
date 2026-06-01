# 🎾 Ranking Pádel Automator

Aplicación para automatizar la gestión del ranking de pádel de un club.
Genera enfrentamientos round-robin, asigna horarios disponibles, detecta conflictos
y exporta todo a Excel.

## Requisitos

- Python 3.11+
- Windows / macOS / Linux

## Instalación rápida (Windows)

```powershell
# 1. Clonar o descomprimir el proyecto
cd ranking-padel-automator

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar Playwright (solo si vas a usar el conector Syltek)
playwright install chromium

# 5. Copiar y rellenar .env
copy .env.example .env
# Edita .env con tus credenciales de Syltek

# 6. Ejecutar la aplicación
streamlit run app.py
```

## Uso sin Syltek (modo CSV)

No necesitas configurar Syltek para empezar. El flujo básico es:

1. Abre `http://localhost:8501` en el navegador.
2. Ve a **⚙️ Configuración** y guarda los parámetros de la fase (fechas, pistas, duración...).
3. Ve a **📥 Importar datos** y sube el CSV de grupos (`sample_data/groups_example.csv`).
4. Ve a **📅 Generar calendario**, pulsa *Generar enfrentamientos* y luego *Asignar horarios*.
5. Revisa el calendario en la tabla.
6. Ve a **📤 Exportar** para descargar el Excel o los mensajes.

## Estructura del proyecto

```
ranking-padel-automator/
├── app.py                  ← Interfaz Streamlit (punto de entrada)
├── requirements.txt
├── .env.example            ← Copia a .env con tus credenciales
├── .gitignore
├── src/
│   ├── config.py           ← Configuración y variables de entorno
│   ├── models.py           ← Modelos Pydantic (Player, Pair, Group, Match...)
│   ├── ranking_generator.py← Generación round-robin de enfrentamientos
│   ├── scheduler.py        ← Asignación de horarios sin conflictos
│   ├── excel_exporter.py   ← Exportación a Excel formateado
│   ├── message_generator.py← Generación de mensajes/emails para jugadores
│   ├── validators.py       ← Validación de datos importados
│   └── syltek_connector.py ← Conector Playwright con Syltek (en desarrollo)
├── sample_data/            ← CSVs de ejemplo para pruebas
├── exports/                ← Excels generados (ignorado por git)
├── debug/                  ← Capturas y HTML de debug de Syltek
└── tests/                  ← Tests con pytest
```

## Ejecutar tests

```powershell
pytest tests/ -v
```

## Conectar con Syltek

El módulo `src/syltek_connector.py` está preparado pero necesita los selectores CSS
específicos de tu instalación de Syltek.

**Pasos para configurarlo:**

1. Abre tu Syltek en Chrome.
2. Pulsa F12 → DevTools.
3. Navega a la sección que quieras automatizar (login, grupos, reservas...).
4. Usa el inspector para encontrar los selectores de los elementos.
5. Abre `src/syltek_connector.py` y busca los comentarios `<<SELECTOR PENDIENTE>>`.
6. Sustituye los selectores de ejemplo por los reales.
7. Prueba el login desde la página **Configuración** de la app.

**Selectores que necesitas identificar:**
- Campo de usuario en la pantalla de login
- Campo de contraseña
- Botón de submit del formulario
- Elemento que aparece solo cuando el login es correcto (ej. nombre de usuario en header)

## Seguridad

- Las credenciales van **siempre** en `.env`, nunca en el código.
- `.env` está en `.gitignore`.
- El modo **dry-run** está activo por defecto: la app nunca crea reservas reales.
- Si Syltek muestra captcha o 2FA, la app se detiene y pide intervención manual.
- Las contraseñas nunca aparecen en logs.

## Formato del CSV de grupos

| Columna | Descripción |
|---------|-------------|
| group_id | ID único del grupo (ej. G1) |
| group_name | Nombre legible (ej. Grupo A) |
| level | Nivel del grupo (opcional) |
| pair_name | Nombre de la pareja |
| player1_name | Nombre del jugador 1 |
| player1_email | Email del jugador 1 (opcional) |
| player1_phone | Teléfono del jugador 1 (opcional) |
| player2_name | Nombre del jugador 2 |
| player2_email | Email del jugador 2 (opcional) |
| player2_phone | Teléfono del jugador 2 (opcional) |

## Formato del CSV de reservas

| Columna | Descripción |
|---------|-------------|
| court_id | ID de la pista (ej. court_1) |
| court_name | Nombre de la pista (ej. Pista 1) |
| start_datetime | Inicio de la reserva (YYYY-MM-DD HH:MM:SS) |
| end_datetime | Fin de la reserva (YYYY-MM-DD HH:MM:SS) |
| description | Descripción opcional |
| source | Origen: syltek o manual |

## Licencia

Uso interno del club. No redistribuir.
