"""
Exporta el calendario al formato de la plantilla del club.

Estructura:
  - Un sheet por NIVEL (todos los grupos del nivel en el mismo sheet)
  - Grupos apilados verticalmente
  - Matriz triangular round-robin por grupo:
      · Col A              = etiqueta fila ("Equipo" / nombre pareja)
      · Cols B .. B+N-2    = cabeceras de columna (parejas 0..N-2)
      · Celda (i, j) con i > j  → triángulo inferior  = partido válido (verde)
      · Celda (i, j) con i <= j → triángulo superior   = gris vacío
  - Contenido de celda programada: "DD/MM/YYYY\\nHH:MM"
"""

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import Group, MatchStatus, RankingPhase, ScheduleResult


# ---------------------------------------------------------------------------
# Colores (iguales a la plantilla)
# ---------------------------------------------------------------------------

C_GREEN        = "A1EB88"   # triángulo inferior — partido programado
C_GREY         = "CCCCCC"   # triángulo superior — celda sin partido
C_RED          = "FDE8E8"   # conflicto
C_TITLE_ACCENT = "4BACC6"   # celda decorativa junto al título de grupo


# ---------------------------------------------------------------------------
# Helpers de estilo
# ---------------------------------------------------------------------------

def _fill(rgb: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=rgb)


def _thin() -> Side:
    return Side(border_style="thin", color="FF000000")


def _border() -> Border:
    s = _thin()
    return Border(left=s, right=s, top=s, bottom=s)


def _font(bold: bool = False, size: int = 10, color: str = "FF000000") -> Font:
    return Font(bold=bold, size=size, color=color, name="Calibri")


def _align(h: str = "center", v: str = "center", wrap: bool = False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


# ---------------------------------------------------------------------------
# Bloque de un grupo
# ---------------------------------------------------------------------------

def _write_group_block(ws, group: Group, match_map: dict, start_row: int) -> int:
    """
    Escribe el bloque de un grupo en ws a partir de start_row.

    Layout:
      start_row      → título "GRUPO X"  +  celda teal en col B
      start_row + 1  → fila en blanco
      start_row + 2  → cabecera: "Equipo" | parejas[0] | parejas[1] | ...
      start_row + 3  → datos pareja 0
      ...
      start_row+2+N  → datos pareja N-1

    Devuelve la primera fila disponible tras el bloque (incluye 3 filas de separación).
    """
    pairs = group.pairs
    N = len(pairs)
    if N < 2:
        ws.cell(row=start_row, column=1).value = f"{group.name} — sin parejas suficientes"
        return start_row + 4

    # Nombre corto del grupo para el título: "GRUPO X"
    group_short = group.name
    if "—" in group_short:
        group_short = group_short.split("—")[-1].strip()
    group_short = group_short.upper()

    # ---- Fila título ----
    title_row = start_row
    tc = ws.cell(row=title_row, column=1)
    tc.value = group_short
    tc.font = Font(bold=True, size=14, name="Calibri", color="FF000000")
    tc.alignment = _align("left", "center")
    ws.row_dimensions[title_row].height = 22

    # Celda decorativa teal junto al título (col B)
    ws.cell(row=title_row, column=2).fill = _fill(C_TITLE_ACCENT)

    # ---- Fila en blanco (start_row + 1) ----
    # (no se escribe nada, simplemente se deja en blanco)

    # ---- Fila cabecera (start_row + 2) ----
    header_row = title_row + 2
    ws.row_dimensions[header_row].height = 34

    hc = ws.cell(row=header_row, column=1)
    hc.value = "Equipo"
    hc.font = _font(bold=True, size=10)
    hc.fill = _fill(C_GREY)
    hc.border = _border()
    hc.alignment = _align("center", "center")

    # Columnas de parejas: pairs[0..N-2]  (N-1 columnas)
    for j in range(N - 1):
        col = 2 + j
        cell = ws.cell(row=header_row, column=col)
        cell.value = pairs[j].display_name
        cell.font = _font(bold=True, size=9)
        cell.fill = _fill(C_GREY)
        cell.border = _border()
        cell.alignment = _align("center", "center", wrap=True)

    # ---- Filas de datos ----
    for i in range(N):
        data_row = header_row + 1 + i
        ws.row_dimensions[data_row].height = 28

        # Col A — nombre de la pareja (etiqueta de fila)
        rh = ws.cell(row=data_row, column=1)
        rh.value = pairs[i].display_name
        rh.font = _font(bold=False, size=9)
        rh.border = _border()
        rh.alignment = _align("left", "center", wrap=True)

        # Columnas B .. B+N-2
        for j in range(N - 1):
            col = 2 + j
            cell = ws.cell(row=data_row, column=col)
            cell.border = _border()
            cell.alignment = _align("center", "center", wrap=True)

            if i <= j:
                # Triángulo superior (incluyendo diagonal) → gris vacío
                cell.fill = _fill(C_GREY)
                cell.value = ""
            else:
                # Triángulo inferior → partido pairs[i] vs pairs[j]
                key = frozenset({pairs[i].id, pairs[j].id})
                match = match_map.get(key)

                if match is None:
                    cell.fill = _fill(C_GREY)
                    cell.value = ""
                elif match.status == MatchStatus.CONFLICT:
                    cell.fill = _fill(C_RED)
                    cell.value = "Sin horario"
                    cell.font = _font(size=8, color="FFB71C1C")
                elif match.suggested_date:
                    cell.fill = _fill(C_GREEN)
                    fecha = match.suggested_date.strftime("%d/%m/%Y")
                    hora = (
                        match.suggested_start_time.strftime("%H:%M")
                        if match.suggested_start_time else ""
                    )
                    cell.value = f"{fecha}\n{hora}" if hora else fecha
                    cell.font = _font(size=9)
                else:
                    cell.fill = _fill(C_GREY)
                    cell.value = ""

    # Devolver primera fila disponible (3 filas de separación)
    last_data_row = header_row + N
    return last_data_row + 4


# ---------------------------------------------------------------------------
# Exportador principal
# ---------------------------------------------------------------------------

def export_groups_to_template(
    result: ScheduleResult,
    phase: RankingPhase,
) -> Path:
    """
    Genera el Excel con la plantilla de grupos del club.
    Un sheet por NIVEL con todos sus grupos apilados.
    """
    # Mapa global: frozenset(pair1_id, pair2_id) → Match
    all_matches = result.scheduled + result.conflicts
    match_map: dict = {}
    for m in all_matches:
        key = frozenset({m.pair_1.id, m.pair_2.id})
        match_map[key] = m

    # Agrupar los grupos por NIVEL
    level_groups: dict[str, list] = defaultdict(list)
    for group in phase.groups:
        level_key = _extract_level_name(group.name)
        level_groups[level_key].append(group)

    # Ordenar niveles numéricamente, grupos dentro de cada nivel también
    sorted_levels = sorted(level_groups.keys(), key=_level_sort_key)

    wb = Workbook()
    wb.remove(wb.active)  # eliminar hoja por defecto

    for level_name in sorted_levels:
        groups = sorted(level_groups[level_name], key=lambda g: _group_sort_key(g.name))

        sheet_name = _safe_sheet_name(level_name.upper())
        ws = wb.create_sheet(title=sheet_name)

        # Ancho de columnas
        ws.column_dimensions["A"].width = 24  # nombres de parejas
        max_N = max((len(g.pairs) for g in groups), default=2)
        for j in range(max_N - 1):
            ws.column_dimensions[get_column_letter(2 + j)].width = 16

        current_row = 2  # una fila de margen superior
        for group in groups:
            current_row = _write_group_block(ws, group, match_map, current_row)

    # Guardar
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = output_dir / f"calendario_plantilla_{ts}.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Helpers de nombres
# ---------------------------------------------------------------------------

def _extract_level_name(group_name: str) -> str:
    """Extrae el nombre del nivel de un nombre de grupo como 'Nivel 3 — Grupo 5'."""
    if "—" in group_name:
        return group_name.split("—")[0].strip()
    m = re.search(r"grupo\s*\d+", group_name, re.I)
    if m:
        return group_name[: m.start()].strip() or group_name
    return group_name


def _level_sort_key(name: str) -> tuple:
    """Ordena niveles numéricamente ('Nivel 3' < 'Nivel 10')."""
    nums = re.findall(r"\d+", name)
    return (int(nums[0]),) if nums else (999, name)


def _group_sort_key(name: str) -> tuple:
    """Ordena grupos numéricamente por el último número del nombre."""
    nums = re.findall(r"\d+", name)
    return (int(nums[-1]),) if nums else (999, name)


def _safe_sheet_name(name: str) -> str:
    """Limpia el nombre para usarlo como nombre de hoja Excel (máx 31 chars)."""
    for ch in r"\/*?:[]":
        name = name.replace(ch, "-")
    name = name.replace("—", "-").strip(" -")
    return name[:31]
