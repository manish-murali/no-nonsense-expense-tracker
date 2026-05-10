"""
Import pipeline: PDF → parser → deduplicate → SQLite.

Usage (via CLI):
    python cli.py import --file statement.pdf --parser sbi_savings \
                         --account-name "SBI Savings" [--password PASS]
"""

import hashlib
from pathlib import Path

from parsers      import PARSER_REGISTRY
from storage      import db
from categorizer  import categorize, seed_defaults
from aliases      import apply_alias
from errors       import Err


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def import_statement(
    pdf_path: str | Path,
    parser_name: str,
    account_name: str,
    password: str | None = None,
    account_number: str | None = None,
    force: bool = False,
    db_path: Path | None = None,
) -> dict:
    """
    Parse a PDF and store new transactions in the DB.

    Returns:
        {
          "found": int,       # total rows parsed
          "inserted": int,    # new rows stored
          "duplicates": int,  # rows already in DB
          "skipped": bool,    # True if PDF was already imported and force=False
        }
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise Err.PDF_NOT_FOUND.format(path=pdf_path)

    if parser_name not in PARSER_REGISTRY:
        raise Err.UNSUPPORTED_PARSER.format(
            parser=parser_name,
            available=", ".join(PARSER_REGISTRY),
        )

    db.init_db(db_path)
    seed_defaults(db_path)

    file_hash = _sha256(pdf_path)
    if not force and db.is_already_imported(file_hash, db_path):
        return {"found": 0, "inserted": 0, "duplicates": 0, "skipped": True}

    entry        = PARSER_REGISTRY[parser_name]
    parse_func   = entry["func"]
    account_type = entry["account_type"]
    bank         = entry["bank"]

    if force:
        db.delete_account_transactions(account_name, account_type, db_path)

    # Call parser — all parsers return list[dict] or dict with "transactions" key
    try:
        result = parse_func(pdf_path, password, account_number)
    except Exception as e:
        if "PDFPasswordIncorrect" in type(e).__name__ or "PDFPasswordIncorrect" in str(e) or "PdfminerException" in type(e).__name__:
            raise Err.WRONG_PASSWORD.format(filename=pdf_path.name) from None
        raise
    if isinstance(result, dict):
        transactions = result.get("transactions", [])
    else:
        transactions = result

    db.upsert_account(account_name, bank, account_type, account_number, db_path)

    inserted   = 0
    duplicates = 0

    for txn in transactions:
        if account_type == "SAVINGS":
            raw_cp = txn.get("counterparty")
            alias  = apply_alias(raw_cp)
            # Keep raw counterparty; store alias separately if it differs
            txn["alias_name"] = alias if alias != raw_cp else None
            cat = categorize(txn, db_path)
            ok  = db.insert_savings_transaction(txn, account_name, cat, db_path)
        else:
            ok  = db.insert_loan_transaction(txn, account_name, db_path)

        if ok:
            inserted += 1
        else:
            duplicates += 1

    found = len(transactions)
    db.log_import(file_hash, pdf_path.name, parser_name, account_name,
                  found, inserted, duplicates, db_path)

    return {
        "found":      found,
        "inserted":   inserted,
        "duplicates": duplicates,
        "skipped":    False,
    }
