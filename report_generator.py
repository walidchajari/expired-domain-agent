import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import settings

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

GREEN_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

COLUMNS = [
    ("Rank", 6),
    ("Domain", 30),
    ("Final Score", 12),
    ("Brandability", 14),
    ("Resale Potential", 18),
    ("Pronounceability", 18),
    ("Memorability", 14),
    ("Startup Potential", 18),
    ("Length", 8),
    ("Reg", 6),
    ("Age/Archive (WBY)", 18),
    ("BL", 8),
    ("DP", 8),
    ("Status", 12),
]


def generate_report(top_domains: list[dict]) -> Path:
    today = datetime.now().strftime("%Y_%m_%d")
    filename = f"Top20Domains_{today}.xlsx"
    filepath = settings.excel_dir / filename

    rows = []
    for rank, d in enumerate(top_domains, start=1):
        rows.append({
            "Rank": rank,
            "Domain": d["domain"],
            "Final Score": d.get("final_score", 0),
            "Brandability": d.get("brandability", 0),
            "Resale Potential": d.get("resale_potential", 0),
            "Pronounceability": d.get("pronounceability", 0),
            "Memorability": d.get("memorability", 0),
            "Startup Potential": d.get("startup_potential", 0),
            "Length": d.get("length", 0),
            "Reg": d.get("reg", 0),
            "Age/Archive (WBY)": d.get("wby", ""),
            "BL": d.get("bl", ""),
            "DP": d.get("dp", ""),
            "Status": d.get("status", ""),
        })

    df = pd.DataFrame(rows)
    df.to_excel(filepath, sheet_name="Top 20 Domains", index=False, engine="openpyxl")
    logger.info("Raw Excel written to %s", filepath)

    _apply_formatting(filepath)
    logger.info("Excel formatting applied")
    return filepath


def _apply_formatting(filepath: Path) -> None:
    wb = load_workbook(filepath)
    ws = wb.active

    col_letters = {}
    for col_idx, (col_name, width) in enumerate(COLUMNS, start=1):
        letter = get_column_letter(col_idx)
        col_letters[col_name] = letter
        ws.column_dimensions[letter].width = width

    # Style header row
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    for col_idx in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER

    # Freeze top row
    ws.freeze_panes = "A2"

    # Data rows
    final_score_col = col_letters.get("Final Score", "C")
    rank_col = col_letters.get("Rank", "A")

    for row_idx in range(2, ws.max_row + 1):
        for col_idx in range(1, len(COLUMNS) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(name="Calibri", size=11)

        # Conditional formatting on Final Score
        score_cell = ws[f"{final_score_col}{row_idx}"]
        try:
            score = float(score_cell.value or 0)
        except (ValueError, TypeError):
            score = 0

        if score > 85:
            fill = GREEN_FILL
        elif score >= 70:
            fill = YELLOW_FILL
        else:
            fill = RED_FILL

        # Apply fill to entire row
        for col_idx in range(1, len(COLUMNS) + 1):
            ws.cell(row=row_idx, column=col_idx).fill = fill

        # Domain column left-aligned
        domain_cell = ws.cell(row=row_idx, column=2)
        domain_cell.alignment = Alignment(horizontal="left", vertical="center")

    # Auto-filter
    last_col = get_column_letter(len(COLUMNS))
    ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"

    wb.save(filepath)


def export_summary_text(top_domains: list[dict]) -> str:
    if not top_domains:
        return "No domains scored today."
    lines = [
        f"Total domains analyzed: {len(top_domains)}",
        f"Top Score: {top_domains[0].get('final_score', 0):.1f}",
        f"Best Domain: {top_domains[0]['domain']}",
        "",
        "Top 5:",
    ]
    for i, d in enumerate(top_domains[:5], 1):
        lines.append(f"  {i}. {d['domain']} ({d.get('final_score', 0):.1f})")
    return "\n".join(lines)
