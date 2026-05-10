import re
from parsers.base import parse_amount, extract_tables_from_pdf, find_header_row, col_index

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def _parse_details(details: str) -> dict:
    details = " ".join(details.split())
    result = {
        "transaction_type": "UNKNOWN",
        "direction":        None,
        "counterparty":     None,
        "counterparty_bank":None,
        "upi_id":           None,
        "reference_number": None,
        "note":             None,
    }

    m = re.search(r"IMPS/(\d+)/([^/]+)/IMPS", details)
    if m:
        result["transaction_type"] = "IMPS"
        result["reference_number"] = m.group(1)
        result["counterparty"]     = m.group(2).strip()
        result["direction"]        = "CREDIT" if "DEP TFR" in details else "DEBIT"
        return result

    m = re.search(r"UPI/(DR|CR)/(\d+)/([^/]+)/([A-Z0-9]+)/([^/]+)/", details)
    if m:
        result["transaction_type"] = "UPI"
        result["direction"]        = "DEBIT" if m.group(1) == "DR" else "CREDIT"
        result["reference_number"] = m.group(2)
        result["counterparty"]     = m.group(3).strip()
        result["counterparty_bank"]= m.group(4)
        result["upi_id"]           = m.group(5).strip()
        return result

    m = re.search(r"(NEFT|RTGS)[- /](\S+)", details, re.IGNORECASE)
    if m:
        result["transaction_type"] = m.group(1).upper()
        result["reference_number"] = m.group(2)
        result["direction"]        = "CREDIT" if "DEP" in details else "DEBIT"
        return result

    m = re.search(r"ACHCr\s+(\S+)\s+(.*)", details)
    if m:
        result["transaction_type"] = "ACH_CREDIT"
        result["direction"]        = "CREDIT"
        result["reference_number"] = m.group(1)
        result["counterparty"]     = m.group(2).strip()
        return result

    m = re.search(r"CEMTEX DEP\s+(\S+)\s+(.*)", details)
    if m:
        result["transaction_type"] = "ACH_CREDIT"
        result["direction"]        = "CREDIT"
        result["reference_number"] = m.group(1)
        result["counterparty"]     = m.group(2).strip()
        return result

    if "ATMCard" in details or "ATM" in details:
        result["transaction_type"] = "ATM_CHARGE"
        result["direction"]        = "DEBIT"
        result["note"]             = details
        return result

    if re.search(r"INTERES", details, re.IGNORECASE):
        result["transaction_type"] = "INTEREST"
        result["direction"]        = "CREDIT"
        result["note"]             = "Interest credit"
        return result

    result["direction"] = "CREDIT" if "DEP" in details or "CR" in details else "DEBIT"
    result["note"]      = details
    return result


def load_statement(pdf_path: str, password: str | None = None,
                   account_number: str | None = None) -> list[dict]:
    raw_rows   = extract_tables_from_pdf(pdf_path, password)
    header_idx = find_header_row(raw_rows, ["date", "details"])

    if header_idx is not None:
        header    = [str(c).strip() if c else "" for c in raw_rows[header_idx]]
        c_date    = col_index(header, ["Date"])
        c_details = col_index(header, ["Details", "Narration", "Description"])
        c_ref     = col_index(header, ["Ref No", "Cheque"])
        c_debit   = col_index(header, ["Debit", "Withdrawal"])
        c_credit  = col_index(header, ["Credit", "Deposit"])
        c_balance = col_index(header, ["Balance"])
        data_rows = raw_rows[header_idx + 1:]
    else:
        # Headerless format: Date | Value Date | Description | Cheque | Debit | Credit | Balance
        c_date, c_details, c_ref, c_debit, c_credit, c_balance = 0, 2, 3, 4, 5, 6
        data_rows = raw_rows

    transactions = []
    for row in data_rows:
        if not any(row):
            continue
        cells = [str(c).strip() if c else "" for c in row]
        max_col = max(filter(None, [c_date, c_details, c_debit, c_credit, c_balance]))
        while len(cells) <= max_col:
            cells.append("")

        date_str = cells[c_date]    if c_date    is not None else ""
        details  = cells[c_details] if c_details is not None else ""
        ref_no   = cells[c_ref]     if c_ref     is not None else ""
        debit    = cells[c_debit]   if c_debit   is not None else ""
        credit   = cells[c_credit]  if c_credit  is not None else ""
        balance  = cells[c_balance] if c_balance is not None else ""

        if not date_str or not details or not _DATE_RE.match(date_str):
            continue

        parsed     = _parse_details(details)
        debit_amt  = parse_amount(debit)
        credit_amt = parse_amount(credit)

        if ref_no and not parsed["reference_number"]:
            parsed["reference_number"] = ref_no.strip()

        transactions.append({
            "bank":             "SBI",
            "account_type":     "SAVINGS",
            "account_number":   account_number,
            "date":             date_str,
            "value_date":       date_str,
            "transaction_type": parsed["transaction_type"],
            "direction":        parsed["direction"],
            "amount":           credit_amt if credit_amt else debit_amt,
            "debit":            debit_amt,
            "credit":           credit_amt,
            "balance":          parse_amount(balance),
            "counterparty":     parsed["counterparty"],
            "counterparty_bank":parsed["counterparty_bank"],
            "upi_id":           parsed["upi_id"],
            "reference_number": parsed["reference_number"],
            "note":             parsed["note"],
            "raw_details":      " ".join(details.split()),
        })

    return transactions
