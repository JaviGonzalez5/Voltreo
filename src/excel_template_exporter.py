"""
Exporta el calendario de cada grupo al formato de la plantilla del club:
matriz triangular round-robin por grupo, un sheet por grupo.

Estructura de cada bloque de grupo:
  - Fila título:    col C  →  "NIVEL X — GRUPO Y"
  - Fila cabecera:  col C  →  "Pareja"  |  cols D..D+N-2 → nombres parejas 2..N
  - Filas datos:    col C  →  nombre pareja i
                   col j  →  ┌ verde (A1EB88):  triángulo inferior (j <= i) duplicado
                              └ data:            partido parejas[i] vs parejas[j]
  - Fila pie:       cols D..D+N-2 mergeadas → resumen del grupo

Colores como en la plantilla:
  Verde  A1EB88 → triangulo inferior / celdas sin partido
  Gris   CCCCCC → celdas de partidos pendientes / cabecera
  Blanco FFFFFF → partido programado
  Rojo   FDE8E8 → conflicto
"""

from datetime import datetime
from itertools import combinations
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter

from .models import Group, Match, MatchStatus, RankingPhase, ScheduleResult


# ---------------------------------------------------------------------------
# Estilos reutilizables
# ---------------------------------------------------------------------------

def _fill(rgb: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=rgb)


def _side(style: str = "medium") -> Side:
    return Side(border_style=style, color="FF000000")


def _border(style: str = "medium") -> Border:
    s = _side(style)
    return Border(left=s, right=s, top=s, bottom=s)


def _font(bold: bool = False, size: int = 11,
          color: str = "FF000000", italic: bool = False) -> Font:
    return Font(bold=bold, size=size, color=color, name="Calibri", italic=italic)


def _align(h: str = "center", v: str = "center", wrap: bool = False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


# Constantes de color (igual que la plantilla)
C_GREEN   = "FFA1EB88"   # triángulo inferior / confirmado
C_GREY    = "FFCCCCCC"   # pendiente / cabecera
C_WHITE   = "FFFFFFFF"   # programado
C_RED     = "FFFDE8E8"   # conflicto
C_TITLE   = "FF1E3A5F"   # azul oscuro para títulos
C_HEADER  = "FFD9E1EC"   # gris azulado para cabeceras de columna


# ---------------------------------------------------------------------------
# Bloque de un grupo
# ---------------------------------------------------------------------------

def _write_group_block(
    ws,
    group: Group,
    match_map: dict,
    start_row: int,
    data_col: int = 3,  # columna C (1-based = 3)
) -> int:
    """
    Escribe el bloque del grupo en ws a partir de start_row.
    Devuelve la primera fila disponible tras el bloque (incluyendo separación).
    """
    pairs = group.pairs
    N = len(pairs)
    if N < 2:
        ws.cell(row=start_row, column=data_col).value = f"{group.name} — sin parejas suficientes"
        return start_row + 3

    # Las columnas de datos son data_col+1 .. data_col+N-1  (= N-1 columnas)
    # data_col   = columna C (fila de pareja)
    # data_col+j = columna de rival pairs[j]  (j=1..N-1)

    # ---- Título ----
    title_row = start_row
    tc = ws.cell(row=title_row, column=data_col)
    tc.value = group.name.upper()
    tc.font = Font(bold=True, size=18, name="Calibri", color=C_TITLE)
    tc.alignment = _align("left", "center")
    ws.row_dimensions[title_row].height = 28

    # ---- Cabecera ----
    header_row = title_row + 1
    ws.row_dimensions[header_row].height = 38  # altura para 2 líneas (nombre pareja)

    # Celda esquina C
    hc = ws.cell(row=header_row, column=data_col)
    hc.value = "Pareja"
    hc.font = _font(bold=True, size=10)
    hc.fill = _fill(C_GREY)
    hc.border = _border()
    hc.alignment = _align("center", "center")

    # Columnas = rivals pairs[1..N-1]
    for j in range(1, N):
        col = data_col + j
        cell = ws.cell(row=header_row, column=col)
        cell.value = pairs[j].display_name
        cell.font = _font(bold=True, size=9)
        cell.fill = _fill(C_HEADER)
        cell.border = _border()
        cell.alignment = _align("center", "center", wrap=True)

    # ---- Filas de datos ----
    group_pair_ids = {p.id for p in pairs}

    for i in range(N):
        data_row = header_row + 1 + i
        ws.row_dimensions[data_row].height = 50  # 3 líneas

        # Col C — nombre de la pareja (fila)
        rh = ws.cell(row=data_row, column=data_col)
        rh.value = pairs[i].display_name
        rh.font = _font(bold=True, size=10)
        rh.border = _border()
        rh.alignment = _align("left", "center", wrap=True)

        for j in range(1, N):
            col = data_col + j
            cell = ws.cell(row=data_row, column=col)
            cell.border = _border()
            cell.alignment = _align("center", "center", wrap=True)

            if j <= i:
                # Triángulo inferior → verde (este partido ya aparece en la fila j)
                cell.fill = _fill(C_GREEN)
                cell.value = ""
                cell.font = _font(size=9)
            else:
                # Partido válido: pairs[i] vs pairs[j]
                key = frozenset({pairs[i].id, pairs[j].id})
                match = match_map.get(key)

                if match is None:
                    # Partido no generado / pendiente
                    cell.fill = _fill(C_GREY)
                    cell.value = "Pendiente"
                    cell.font = _font(size=9, color="FF888888", italic=True)

                elif match.status == MatchStatus.CONFLICT:
                    cell.fill = _fill(C_RED)
                    cell.value = "⚠️ Sin horario\n(conflicto)"
                    cell.font = _font(size=9, color="FFB71C1C")

                elif match.suggested_date:
                    # Partido programado
                    cell.fill = _fill(C_WHITE)
                    fecha = match.suggested_date.strftime("%d/%m/%Y")
                    hora  = (match.suggested_start_time.strftime("%H:%M")
                             if match.suggested_start_time else "—")
                    pista = match.court.name if match.court else "—"
                    cell.value = f"{fecha}\n{hora}\n{pista}"
                    cell.font = _font(size=9)

                else:
                    cell.fill = _fill(C_GREY)
                    cell.value = "Pendiente"
                    cell.font = _font(size=9, color="FF888888", italic=True)

    # ---- Pie (fila resumen) ----
    footer_row = header_row + 1 + N
    ws.row_dimensions[footer_row].height = 18

    # Calcular stats del grupo
    n_sched = 0
    n_conf  = 0
    for key, m in match_map.items():
        if key.issubset(group_pair_ids):
            if m.status in (MatchStatus.SCHEDULED, MatchStatus.MANUALLY_MODIFIED):
                n_sched += 1
            elif m.status == MatchStatus.CONFLICT:
                n_conf += 1
    n_total = n_sched + n_conf

    # Merge pie: data_col+1 .. data_col+N-1
    fc_start = data_col + 1
    fc_end   = data_col + N - 1
    if fc_end > fc_start:
        ws.merge_cells(
            start_row=footer_row, start_column=fc_start,
            end_row=footer_row,   end_column=fc_end,
        )
    footer_cell = ws.cell(row=footer_row, column=fc_start)
    footer_cell.value = (
        f"{n_total} partidos  ·  {n_sched} programados  ·  {n_conf} conflictos"
    )
    footer_cell.font = _font(bold=True, size=10)
    footer_cell.border = _border()
    footer_cell.alignment = _align("center", "center")

    # Celda C del pie (sin borde / vacía)
    ws.cell(row=footer_row, column=data_col).value = ""

    return footer_row + 4  # 3 filas en blanco de separación + 1


# ---------------------------------------------------------------------------
# Exportador principal
# ---------------------------------------------------------------------------

def export_groups_to_template(
    result: ScheduleResult,
    phase: RankingPhase,
) -> Path:
    """
    Genera el Excel con la plantilla de grupos del club.
    Un sheet por grupo, con la matriz triangular round-robin.
    """
    # Mapa global: frozenset(pair1_id, pair2_id) → Match
    all_matches = result.scheduled + result.conflicts
    match_map: dict = {}
    for m in all_matches:
        key = frozenset({m.pair_1.id, m.pair_2.id})
        match_map[key] = m

    wb = Workbook()
    wb.remove(wb.active)  # eliminar hoja por defecto

    # ---- Hoja resumen ----
    ws_res = wb.create_sheet(title="Resumen")
    _write_summary_sheet(ws_res, phase, result, match_map)

    # ---- Una hoja por grupo ----
    groups_sorted = sorted(phase.groups, key=lambda g: g.name)
    for group in groups_sorted:
        # Nombre de hoja: máx 31 chars, sin caracteres prohibidos
        raw = group.name[:31]
        for ch in r'\/*?:[]':
            raw = raw.replace(ch, "-")
        raw = raw.replace("—", "-").strip(" -")
        sheet_name = raw[:31]

        ws = wb.create_sheet(title=sheet_name)

        N = len(group.pairs)
        # Anchos de columnas
        ws.column_dimensions["A"].width = 3
        ws.column_dimensions["B"].width = 3
        ws.column_dimensions[get_column_letter(3)].width = 26  # col C: nombres de pareja
        for j in range(1, max(N, 2)):
            ws.column_dimensions[get_column_letter(3 + j)].width = 15

        _write_group_block(ws, group, match_map, start_row=4, data_col=3)

    # ---- Guardar ----
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = output_dir / f"calendario_plantilla_{ts}.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Hoja resumen
# ---------------------------------------------------------------------------

def _write_summary_sheet(ws, phase, result: ScheduleResult, match_map: dict):
    """Escribe una hoja de resumen con todos los grupos."""
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 14

    # Título
    ws["A1"] = f"RANKING PÁDEL — {phase.name.upper()}"
    ws["A1"].font = Font(bold=True, size=16, name="Calibri", color=C_TITLE)
    ws["A1"].alignment = _align("left")
    ws["A2"] = f"Fase: {phase.start_date.strftime('%d/%m/%Y')} → {phase.end_date.strftime('%d/%m/%Y')}"
    ws["A2"].font = _font(size=11, italic=True)
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[3].height = 6  # espacio

    # Cabecera tabla
    headers = ["Grupo", "Parejas", "Partidos", "Programados", "Conflictos"]
    for ci, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=ci)
        cell.value = h
        cell.font = _font(bold=True, size=11, color="FFFFFFFF")
        cell.fill = _fill(C_TITLE)
        cell.border = _border("thin")
        cell.alignment = _align("center", "center")
    ws.row_dimensions[4].height = 20

    groups_sorted = sorted(phase.groups, key=lambda g: g.name)
    for ri, group in enumerate(groups_sorted, start=5):
        gids = {p.id for p in group.pairs}
        n_sched = sum(
            1 for k, m in match_map.items()
            if k.issubset(gids)
            and m.status in (MatchStatus.SCHEDULED, MatchStatus.MANUALLY_MODIFIED)
        )
        n_conf = sum(
            1 for k, m in match_map.items()
            if k.issubset(gids) and m.status == MatchStatus.CONFLICT
        )
        n_total = n_sched + n_conf
        n_pairs = len(group.pairs)

        row_data = [group.name, n_pairs, n_total, n_sched, n_conf]
        bg = "FFFAFAFA" if ri % 2 == 0 else "FFFFFFFF"
        for ci, val in enumerate(row_data, start=1):
            cell = ws.cell(row=ri, column=ci)
            cell.value = val
            cell.font = _font(size=10)
            cell.fill = _fill(bg)
            cell.border = _border("thin")
            cell.alignment = _align("left" if ci == 1 else "center", "center")
        ws.row_dimensions[ri].height = 16

    # Totales
    total_row = 5 + len(groups_sorted)
    ws.row_dimensions[total_row].height = 18
    total_sched = result.scheduled_count
    total_conf  = result.conflict_count
    total_all   = result.total_matches
    for ci, val in enumerate(
        ["TOTAL", sum(len(g.pairs) for g in groups_sorted), total_all, total_sched, total_conf],
        start=1,
    ):
        cell = ws.cell(row=total_row, column=ci)
        cell.value = val
        cell.font = _font(bold=True, size=11, color="FFFFFFFF")
        cell.fill = _fill(C_TITLE)
        cell.border = _border("thin")
        cell.alignment = _align("left" if ci == 1 else "center", "center")
