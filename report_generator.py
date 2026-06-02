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

SHEET_CONFIG = {
    "Top 20": {
        "columns": [
            ("Rank", 6), ("Domain", 30), ("Category", 22),
            ("Final Score", 12), ("Est. Wholesale Value", 22),
            ("Est. End User Value", 22), ("Probability of Sale", 20),
            ("Reason for Selection", 60),
        ],
        "header_fill": HEADER_FILL,
        "score_col": "D",
    },
}


COL_KEY_MAP = {
    "Category": "category",
    "Final Score": "final_score",
    "Est. Wholesale Value": "estimated_wholesale_price",
    "Est. End User Value": "estimated_end_user_price",
    "Probability of Sale": "probability_of_sale",
    "Reason for Selection": "reason_for_selection",
}

def _build_rows(domains: list[dict], columns: list[tuple]) -> list[dict]:
    rows = []
    for rank, d in enumerate(domains, start=1):
        row = {"Rank": rank}
        for col_name, _ in columns:
            if col_name == "Rank":
                continue
            key = COL_KEY_MAP.get(col_name, col_name.lower().replace(" ", "_"))
            val = d.get(key, "")
            if col_name == "Probability of Sale":
                val = f"{val:.0f}%" if isinstance(val, (int, float)) else val
            elif col_name == "Final Score":
                val = round(val, 2) if isinstance(val, (int, float)) else val
            row[col_name] = val
        rows.append(row)
    return rows


def _collect_sheet_data(sheet_name: str, config: dict, domains: list[dict]) -> pd.DataFrame:
    columns = config["columns"]
    rows = _build_rows(domains, columns)
    return pd.DataFrame(rows)


def _apply_formatting(filepath: Path) -> None:
    wb = load_workbook(filepath)

    def fmt_sheet(ws, config: dict):
        columns = config["columns"]
        header_fill = config["header_fill"]
        score_col = config["score_col"]

        col_letters = {}
        for col_idx, (col_name, width) in enumerate(columns, start=1):
            letter = get_column_letter(col_idx)
            col_letters[col_name] = letter
            ws.column_dimensions[letter].width = width

        for col_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN_BORDER

        ws.freeze_panes = "A2"

        for row_idx in range(2, ws.max_row + 1):
            for col_idx in range(1, len(columns) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = THIN_BORDER
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(name="Calibri", size=11)

            ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="left", vertical="center")

            score_cell = ws[f"{score_col}{row_idx}"]
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

            for col_idx in range(1, len(columns) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = fill

        last_col = get_column_letter(len(columns))
        ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"

    for sheet_name, config in SHEET_CONFIG.items():
        if sheet_name in wb.sheetnames:
            fmt_sheet(wb[sheet_name], config)

    wb.save(filepath)


def generate_report(rankings: dict) -> Path:
    today = datetime.now().strftime("%Y_%m_%d")
    filename = f"Top20Domains_{today}.xlsx"
    filepath = settings.excel_dir / filename

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, config in SHEET_CONFIG.items():
            domains = rankings.get("overall", [])
            df = _collect_sheet_data(sheet_name, config, domains)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    _apply_formatting(filepath)
    logger.info("Report generated: %s", filepath)
    return filepath


def export_summary_text(top_domains: list[dict]) -> str:
    if not top_domains:
        return "No domains scored today."
    lines = [
        f"Total domains analyzed: {len(top_domains)}",
        f"Top Score: {top_domains[0].get('final_score', 0):.1f}",
        f"Best Domain: {top_domains[0]['domain']}",
        f"Category: {top_domains[0].get('category', 'N/A')}",
        "",
        "Top 5:",
    ]
    for i, d in enumerate(top_domains[:5], 1):
        cat = d.get("category", "")
        geo = d.get("geo_score", 0)
        extra = f" [{cat}]" if cat else ""
        if geo:
            extra += f" (Geo: {geo})"
        lines.append(f"  {i}. {d['domain']} ({d.get('final_score', 0):.1f}){extra}")
    return "\n".join(lines)
