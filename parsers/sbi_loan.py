import re
from parsers.base import parse_amount, extract_text_from_pdf, extract_tables_from_pdf


def _parse_transaction_type(details: str) -> dict:
    details_clean = " ".join(details.split()).upper()
    txn_type  = "UNKNOWN"
    reference = None

    if "PRINCIPAL REPAYMENT" in details_clean:
        txn_type = "PRINCIPAL_REPAYMENT"
    elif "INTEREST REPAYMENT" in details_clean:
        txn_type = "INTEREST_REPAYMENT"
    elif "COMPOUND REPAYMENT" in details_clean:
        txn_type = "COMPOUND_REPAYMENT"

    m = re.search(r"IMPS/(\d+)/", details_clean)
    if m:
        reference = m.group(1)

    return {"transaction_type": txn_type, "reference_number": reference}


def _extract_account_summary(text: str) -> dict:
    def find(pattern):
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    return {
        "account_number":     find(r"Account No\s*:\s*([\d]+)"),
        "sanctioned_amount":  find(r"Sanctioned Amount\s*:\s*([\d,\.]+)"),
        "outstanding_amount": find(r"Outstanding Amount\s*:\s*([\d,\.]+)"),
        "rate_of_interest":   find(r"Rate of Interest\s*:\s*([\d\.]+%)"),
        "loan_term":          find(r"Loan Term\s*:\s*([\d]+ Months)"),
        "remaining_tenure":   find(r"Remaining Tenure\s*:\s*([\d]+ Months)"),
        "product":            find(r"Product\s*:\s*(.+?)\n"),
        "account_open_date":  find(r"Account open Date\s*:\s*([\d\-]+)"),
        "ifsc_code":          find(r"IFSC Code\s*:\s*(\S+)"),
    }


def load_statement(pdf_path: str, password: str | None = None,
                   account_number: str | None = None) -> list[dict]:
    full_text       = extract_text_from_pdf(pdf_path, password)
    account_summary = _extract_account_summary(full_text)
    acct_num        = account_summary.get("account_number") or account_number

    transactions = []
    raw_rows = []
    import pdfplumber
    kwargs = {"password": password} if password else {}
    with pdfplumber.open(pdf_path, **kwargs) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                raw_rows.extend(table)

    for table_start, row in enumerate(raw_rows):
        header = [str(h).strip() if h else "" for h in row]
        if "Post Date" not in header:
            continue
        col = {name: i for i, name in enumerate(header)}
        for row in raw_rows[table_start + 1:]:
            if not any(row):
                continue
            post_date  = (row[col.get("Post Date",  0)] or "").strip()
            value_date = (row[col.get("Value Date", 1)] or "").strip()
            details    = row[col.get("Details",     2)] or ""
            ref_no     = row[col.get("Ref No/Cheque", 3)] or ""
            debit      = row[col.get("Debit",       4)] or ""
            credit     = row[col.get("Credit",      5)] or ""
            balance    = row[col.get("Balance",     6)] or ""

            if not post_date:
                continue

            parsed     = _parse_transaction_type(details)
            debit_amt  = parse_amount(debit)
            credit_amt = parse_amount(credit)

            if ref_no.strip() not in ("-", "") and not parsed["reference_number"]:
                parsed["reference_number"] = ref_no.strip()

            transactions.append({
                "bank":             "SBI",
                "account_type":     "LOAN",
                "account_number":   acct_num,
                "date":             post_date,
                "value_date":       value_date or post_date,
                "transaction_type": parsed["transaction_type"],
                "direction":        "CREDIT" if credit_amt else ("DEBIT" if debit_amt else None),
                "amount":           credit_amt if credit_amt else debit_amt,
                "debit":            debit_amt,
                "credit":           credit_amt,
                "balance":          parse_amount(balance),
                "payment_method":   "IMPS" if parsed["reference_number"] else None,
                "reference_number": parsed["reference_number"],
                "raw_details":      " ".join(str(details).split()),
            })
        break  # only first matching table

    return transactions
