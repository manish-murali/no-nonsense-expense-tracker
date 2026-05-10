"""
Expense Tracker — Centralised error definitions.

Usage:
    from errors import Err
    raise Err.WRONG_PASSWORD.format(filename="statement.pdf")
"""


class AppError(Exception):
    def __init__(self, code: str, message: str):
        self.code    = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class _ErrorDef:
    def __init__(self, code: str, template: str):
        self.code     = code
        self.template = template

    def format(self, **kwargs) -> AppError:
        return AppError(self.code, self.template.format(**kwargs))

    def exc(self) -> AppError:
        return AppError(self.code, self.template)


class Err:
    # ── PDF / Import ──────────────────────────────────────────────────
    WRONG_PASSWORD = _ErrorDef(
        "PDF_001",
        "Wrong password for '{filename}'. Update the password in config.json.",
    )
    PDF_NOT_FOUND = _ErrorDef(
        "PDF_002",
        "PDF file not found: '{path}'.",
    )
    NO_TRANSACTIONS = _ErrorDef(
        "PDF_003",
        "No transactions found in '{filename}'. The PDF may be empty or unsupported.",
    )
    UNSUPPORTED_PARSER = _ErrorDef(
        "PDF_004",
        "Unknown parser '{parser}'. Available parsers: {available}.",
    )
    HEADER_NOT_FOUND = _ErrorDef(
        "PDF_005",
        "Could not find transaction table headers in '{filename}'.",
    )

    # ── Config ────────────────────────────────────────────────────────
    CONFIG_NOT_FOUND = _ErrorDef(
        "CFG_001",
        "config.json not found at '{path}'. Create it to use import-all.",
    )
    CONFIG_PLACEHOLDER_PASSWORD = _ErrorDef(
        "CFG_002",
        "Password not set for '{account}' in config.json — skipped.",
    )
    CONFIG_FOLDER_NOT_FOUND = _ErrorDef(
        "CFG_003",
        "Statement folder not found for '{account}': '{folder}'.",
    )

    # ── Database ──────────────────────────────────────────────────────
    DB_INSERT_FAILED = _ErrorDef(
        "DB_001",
        "Failed to insert transaction '{txn_id}' into the database.",
    )
    DB_MIGRATION_FAILED = _ErrorDef(
        "DB_002",
        "Database migration failed for table '{table}': {reason}.",
    )
