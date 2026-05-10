import re
from parsers.base import parse_amount, extract_tables_from_pdf, find_header_row, col_index


def _parse_details(details: str) -> dict:
    details_clean = " ".join(details.split())
    result = {
        "transaction_type": "UNKNOWN",
        "direction_hint":   None,
        "counterparty":     None,
        "counterparty_bank":None,
        "upi_id":           None,
        "reference_number": None,
        "note":             None,
    }

    m = re.match(r"IMPS/P2A/(\d+)/([^/]+)/([^/]*)/([^/]*)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "IMPS"
        result["reference_number"] = m.group(1)
        result["counterparty"]     = m.group(2).strip()
        result["counterparty_bank"]= m.group(4).strip() or None
        return result

    m = re.match(r"IMPS TO ID[:\s]+(.+?)\s*\((\d+)\)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "IMPS"
        result["counterparty"]     = m.group(1).strip()
        result["reference_number"] = m.group(2)
        result["direction_hint"]   = "DEBIT"
        return result

    m = re.match(r"NEFT TRANSFER FROM (.+?)\s*\(([^)]+)\)\s*\(([^)]+)\)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "NEFT"
        result["counterparty"]     = m.group(1).strip()
        result["counterparty_bank"]= m.group(2).strip()
        result["reference_number"] = m.group(3).strip()
        result["direction_hint"]   = "CREDIT"
        return result

    # Slash-delimited inward NEFT:  NEFT/<ref>/<counterparty>/<bank>/<note>
    m = re.match(r"NEFT/([^/]+)/(.+?)/([^/]+)/(.+)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "NEFT"
        result["reference_number"] = m.group(1).strip()
        result["counterparty"]     = m.group(2).strip()
        result["counterparty_bank"]= m.group(3).strip()
        result["note"]             = m.group(4).strip()
        return result

    if re.search(r"NEFT", details_clean, re.IGNORECASE):
        result["transaction_type"] = "NEFT"
        result["note"]             = details_clean
        return result

    m = re.search(r"UPI/(CR|DR)/(\d+)/([^/]+)/([A-Z0-9]+)/([^/]+)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "UPI"
        result["direction_hint"]   = "CREDIT" if m.group(1).upper() == "CR" else "DEBIT"
        result["reference_number"] = m.group(2)
        result["counterparty"]     = m.group(3).strip()
        result["counterparty_bank"]= m.group(4)
        result["upi_id"]           = m.group(5).strip()
        return result

    m = re.search(r"RTGS[/ ](\S+)", details_clean, re.IGNORECASE)
    if m:
        result["transaction_type"] = "RTGS"
        result["reference_number"] = m.group(1)
        result["note"]             = details_clean
        return result

    if re.search(r"ATM", details_clean, re.IGNORECASE):
        result["transaction_type"] = "ATM_CHARGE"
        result["direction_hint"]   = "DEBIT"
        result["note"]             = details_clean
        return result

    if re.search(r"INTEREST", details_clean, re.IGNORECASE):
        result["transaction_type"] = "INTEREST"
        result["direction_hint"]   = "CREDIT"
        result["note"]             = details_clean
        return result

    if re.search(r"CHARGE|FEE|GST|TAX", details_clean, re.IGNORECASE):
        result["transaction_type"] = "CHARGE"
        result["direction_hint"]   = "DEBIT"
        result["note"]             = details_clean
        return result

    result["note"] = details_clean
    return result


def load_statement(pdf_path: str, password: str | None = None,
                   account_number: str | None = None) -> list[dict]:
    raw_rows   = extract_tables_from_pdf(pdf_path, password)
    header_idx = find_header_row(raw_rows, ["debit", "credit", "balance"])
    if header_idx is None:
        from errors import Err
        raise Err.HEADER_NOT_FOUND.format(filename=str(pdf_path))

    header     = [str(c).strip() if c else "" for c in raw_rows[header_idx]]
    c_date     = col_index(header, ["Date"])
    c_details  = col_index(header, ["Transaction details", "Narration", "Description", "Particulars"])
    c_chq      = col_index(header, ["Chq", "Cheque"])
    c_withdraw = col_index(header, ["Withdrawal", "Debit"])
    c_deposit  = col_index(header, ["Deposit", "Credit"])
    c_balance  = col_index(header, ["Balance"])

    transactions = []
    for row in raw_rows[header_idx + 1:]:
        if not any(row):
            continue
        cells = [str(c).strip() if c else "" for c in row]
        while len(cells) <= max(filter(None, [c_date, c_details, c_withdraw, c_deposit, c_balance])):
            cells.append("")

        date_val    = cells[c_date]     if c_date     is not None else ""
        details_val = cells[c_details]  if c_details  is not None else ""
        chq_val     = cells[c_chq]      if c_chq      is not None else ""
        withdraw    = cells[c_withdraw] if c_withdraw  is not None else ""
        deposit     = cells[c_deposit]  if c_deposit  is not None else ""
        balance     = cells[c_balance]  if c_balance  is not None else ""

        details_upper = details_val.upper()
        if "OPENING BALANCE" in details_upper or "CLOSING BALANCE" in details_upper:
            continue
        if "TOTAL" in details_upper and not date_val:
            continue
        if not date_val:
            continue

        withdraw_amt = parse_amount(withdraw)
        deposit_amt  = parse_amount(deposit)
        parsed       = _parse_details(details_val)
        direction    = ("DEBIT"   if withdraw_amt else
                        "CREDIT"  if deposit_amt  else
                        parsed.get("direction_hint") or "UNKNOWN")
        amount = deposit_amt if direction == "CREDIT" else withdraw_amt

        transactions.append({
            "bank":             "AXIS",
            "account_type":     "SAVINGS",
            "account_number":   account_number,
            "date":             date_val,
            "value_date":       date_val,
            "transaction_type": parsed["transaction_type"],
            "direction":        direction,
            "amount":           amount,
            "debit":            withdraw_amt,
            "credit":           deposit_amt,
            "balance":          parse_amount(balance),
            "counterparty":     parsed["counterparty"],
            "counterparty_bank":parsed["counterparty_bank"],
            "upi_id":           parsed["upi_id"],
            "reference_number": parsed["reference_number"] or chq_val or None,
            "note":             parsed["note"],
            "raw_details":      " ".join(details_val.split()),
        })

    return transactions
