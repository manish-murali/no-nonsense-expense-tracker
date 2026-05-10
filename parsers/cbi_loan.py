import re
from parsers.base import parse_amount, extract_tables_from_pdf, find_header_row, col_index


def _parse_balance(value: str) -> tuple[float | None, str | None]:
    if not value or str(value).strip() in ("-", "", "None"):
        return None, None
    raw = str(value).strip().upper()
    indicator = None
    if raw.endswith("DR"):
        indicator, raw = "DR", raw[:-2].strip()
    elif raw.endswith("CR"):
        indicator, raw = "CR", raw[:-2].strip()
    try:
        return float(raw.replace(",", "")), indicator
    except ValueError:
        return None, indicator


def _parse_description(desc: str) -> dict:
    desc_clean = " ".join(desc.split()).upper()
    result = {"transaction_type": "UNKNOWN", "direction_hint": None, "note": None}

    if "PART PERIOD INTEREST" in desc_clean or "INTEREST" in desc_clean:
        result["transaction_type"] = "INTEREST_CHARGE"
        result["direction_hint"]   = "DEBIT"
    elif "DEPOSIT TRANSFER" in desc_clean:
        result["transaction_type"] = "DEPOSIT_TRANSFER"
        result["direction_hint"]   = "CREDIT"
    elif "NPB REPAYMENT" in desc_clean or "REPAYMENT FROM GL" in desc_clean or "PRINCIPAL" in desc_clean:
        result["transaction_type"] = "PRINCIPAL_REPAYMENT"
        result["direction_hint"]   = "CREDIT"
    elif "PENAL" in desc_clean or "PENALTY" in desc_clean:
        result["transaction_type"] = "PENAL_INTEREST"
        result["direction_hint"]   = "DEBIT"
    elif "DISBURSEMENT" in desc_clean or "DISBURSE" in desc_clean:
        result["transaction_type"] = "DISBURSEMENT"
        result["direction_hint"]   = "DEBIT"
    elif "CHARGE" in desc_clean or "FEE" in desc_clean or "GST" in desc_clean:
        result["transaction_type"] = "CHARGE"
        result["direction_hint"]   = "DEBIT"
    else:
        result["note"] = " ".join(desc.split())

    return result


def load_statement(pdf_path: str, password: str | None = None,
                   account_number: str | None = None) -> list[dict]:
    raw_rows   = extract_tables_from_pdf(pdf_path, password)
    header_idx = find_header_row(raw_rows, ["post date", "date"])
    if header_idx is None:
        raise ValueError("Could not find transaction table headers in the PDF.")

    header       = [str(c).strip() if c else "" for c in raw_rows[header_idx]]
    c_post_date  = col_index(header, ["Post Date"])
    c_value_date = col_index(header, ["Value Date"])
    c_cheque     = col_index(header, ["Cheque"])
    c_desc       = col_index(header, ["Account Description", "Description", "Narration", "Particulars"])
    c_debit      = col_index(header, ["Debit"])
    c_credit     = col_index(header, ["Credit"])
    c_balance    = col_index(header, ["Balance"])

    transactions = []
    for row in raw_rows[header_idx + 1:]:
        if not any(row):
            continue
        cells = [str(c).strip() if c else "" for c in row]
        max_col = max(filter(None, [c_post_date, c_value_date, c_desc, c_debit, c_credit, c_balance]))
        while len(cells) <= max_col:
            cells.append("")

        post_date   = cells[c_post_date]  if c_post_date  is not None else ""
        value_date  = cells[c_value_date] if c_value_date is not None else ""
        cheque      = cells[c_cheque]     if c_cheque     is not None else ""
        description = cells[c_desc]       if c_desc       is not None else ""
        debit_raw   = cells[c_debit]      if c_debit      is not None else ""
        credit_raw  = cells[c_credit]     if c_credit     is not None else ""
        balance_raw = cells[c_balance]    if c_balance     is not None else ""

        if not post_date or not re.match(r"\d{2}/\d{2}/\d{4}", post_date):
            continue

        debit_amt              = parse_amount(debit_raw)
        credit_amt             = parse_amount(credit_raw)
        balance_amt, bal_ind   = _parse_balance(balance_raw)
        parsed                 = _parse_description(description)
        direction              = ("CREDIT" if credit_amt else
                                  "DEBIT"  if debit_amt  else
                                  parsed.get("direction_hint") or "UNKNOWN")
        amount = credit_amt if direction == "CREDIT" else debit_amt

        transactions.append({
            "bank":              "CBI",
            "account_type":      "LOAN",
            "account_number":    account_number,
            "date":              post_date,
            "value_date":        value_date or post_date,
            "transaction_type":  parsed["transaction_type"],
            "direction":         direction,
            "amount":            amount,
            "debit":             debit_amt,
            "credit":            credit_amt,
            "balance":           balance_amt,
            "balance_indicator": bal_ind,
            "cheque_number":     cheque or None,
            "note":              parsed["note"],
            "raw_details":       " ".join(description.split()),
        })

    return transactions
