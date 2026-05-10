import re
import pdfplumber


def parse_amount(value) -> float | None:
    if value is None or str(value).strip() in ("", "-", "None", "0.00"):
        return None
    try:
        result = float(str(value).replace(",", "").strip())
        return result if result != 0.0 else None
    except ValueError:
        return None


def extract_tables_from_pdf(pdf_path: str, password: str | None = None) -> list[list]:
    rows = []
    kwargs = {"password": password} if password else {}
    with pdfplumber.open(pdf_path, **kwargs) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return rows


def extract_text_from_pdf(pdf_path: str, password: str | None = None) -> str:
    kwargs = {"password": password} if password else {}
    text = ""
    with pdfplumber.open(pdf_path, **kwargs) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text


def find_header_row(rows: list[list], keys: list[str]) -> int | None:
    for i, row in enumerate(rows):
        cells = [str(c).strip().lower() if c else "" for c in row]
        if any(k.lower() in cells for k in keys):
            return i
    return None


def col_index(header: list[str], names: list[str]) -> int | None:
    for name in names:
        for i, h in enumerate(header):
            if name.lower() in h.lower():
                return i
    return None


def normalize_date(date_str: str) -> str:
    """Convert DD/MM/YYYY or DD-MM-YYYY to YYYY-MM-DD for SQLite range queries."""
    try:
        parts = date_str.replace("-", "/").split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            d, m, y = parts
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return date_str
