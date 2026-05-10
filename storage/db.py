import hashlib
import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).parent.parent / "tracker.db"


def get_db_path() -> Path:
    return Path(os.environ.get("TRACKER_DB", DEFAULT_DB))


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _make_txn_id(txn: dict, account_name: str) -> str:
    key = txn.get("raw_details") or ""
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _normalize_date(date_str: str) -> str:
    """Any date string → YYYY-MM-DD (for SQL queries)."""
    try:
        parts = str(date_str).replace("-", "/").split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            d, m, y = parts
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return date_str


def _display_date(date_str: str) -> str:
    """Any date string → DD/MM/YYYY (display format)."""
    try:
        parts = str(date_str).replace("-", "/").split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            d, m, y = parts
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
    except Exception:
        pass
    return date_str


# ── Schema ────────────────────────────────────────────────────────────

_SAVINGS_DDL = """
    CREATE TABLE IF NOT EXISTS savings_transactions (
        txn_id            TEXT PRIMARY KEY,
        bank              TEXT,
        account_name      TEXT,
        account_number    TEXT,
        date              TEXT,
        date_iso          TEXT,
        value_date        TEXT,
        transaction_type  TEXT,
        direction         TEXT,
        amount            REAL,
        debit             REAL,
        credit            REAL,
        balance           REAL,
        counterparty      TEXT,
        counterparty_bank TEXT,
        upi_id            TEXT,
        reference_number  TEXT,
        note              TEXT,
        raw_details       TEXT,
        alias_name        TEXT,
        category          TEXT,
        subcategory       TEXT,
        imported_at       TEXT DEFAULT (datetime('now'))
    );
"""

_LOAN_DDL = """
    CREATE TABLE IF NOT EXISTS loan_transactions (
        txn_id           TEXT PRIMARY KEY,
        bank             TEXT,
        account_name     TEXT,
        account_number   TEXT,
        date             TEXT,
        date_iso         TEXT,
        value_date       TEXT,
        transaction_type TEXT,
        direction        TEXT,
        amount           REAL,
        debit            REAL,
        credit           REAL,
        balance          REAL,
        extra_data       TEXT,
        raw_details      TEXT,
        imported_at      TEXT DEFAULT (datetime('now'))
    );
"""


def init_db(db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    with conn:
        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS accounts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name   TEXT UNIQUE NOT NULL,
                bank           TEXT NOT NULL,
                account_type   TEXT NOT NULL,
                account_number TEXT,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            {_SAVINGS_DDL}
            {_LOAN_DDL}

            CREATE TABLE IF NOT EXISTS import_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash    TEXT UNIQUE,
                filename     TEXT,
                parser       TEXT,
                account_name TEXT,
                imported_at  TEXT DEFAULT (datetime('now')),
                found        INTEGER DEFAULT 0,
                inserted     INTEGER DEFAULT 0,
                duplicates   INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_sav_date  ON savings_transactions(date_iso);
            CREATE INDEX IF NOT EXISTS idx_sav_dir   ON savings_transactions(direction);
            CREATE INDEX IF NOT EXISTS idx_sav_cat   ON savings_transactions(category);
            CREATE INDEX IF NOT EXISTS idx_sav_acct  ON savings_transactions(account_name);
            CREATE INDEX IF NOT EXISTS idx_loan_date ON loan_transactions(date_iso);
            CREATE INDEX IF NOT EXISTS idx_loan_acct ON loan_transactions(account_name);
        """)

    _migrate_drop_id(conn, db_path)
    _migrate_date_format(conn)
    _migrate_add_subcategory(conn)
    _migrate_conversations(conn)
    conn.close()


def _migrate_drop_id(conn: sqlite3.Connection, db_path: Path | None) -> None:
    """
    One-time migration: if either transaction table still has an 'id' column,
    recreate it with txn_id as the sole primary key and copy all data across.
    """
    for tbl, ddl in (("savings_transactions", _SAVINGS_DDL),
                     ("loan_transactions",    _LOAN_DDL)):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if "id" not in cols:
            continue  # already migrated

        tmp = f"{tbl}_new"
        # Ensure txn_id is populated before migrating (backfill if needed)
        _backfill_txn_ids_for(conn, tbl)

        conn.execute(ddl.replace(
            f"CREATE TABLE IF NOT EXISTS {tbl}",
            f"CREATE TABLE {tmp}"
        ))
        shared = [c for c in cols if c != "id" and c in _table_columns(conn, tmp)]
        col_list = ", ".join(shared)
        conn.execute(f"INSERT OR IGNORE INTO {tmp} ({col_list}) SELECT {col_list} FROM {tbl}")
        conn.execute(f"DROP TABLE {tbl}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {tbl}")
        conn.commit()


def _migrate_date_format(conn: sqlite3.Connection) -> None:
    """One-time migration: flip stored dates from MM/DD/YYYY → DD/MM/YYYY.
    Detects MM/DD/YYYY by finding any date where the second part > 12
    (impossible as a month in DD/MM/YYYY, but possible as a day in MM/DD/YYYY).
    """
    # If ANY date has second part > 12, the format is MM/DD → flip all
    needs_flip = conn.execute(
        "SELECT 1 FROM savings_transactions "
        "WHERE date GLOB '??/??/????' AND CAST(substr(date,4,2) AS INTEGER) > 12 LIMIT 1"
    ).fetchone()
    if not needs_flip:
        return   # Already DD/MM/YYYY or no data
    conn.execute("""
        UPDATE savings_transactions
        SET date = substr(date,4,2) || '/' || substr(date,1,2) || '/' || substr(date,7)
        WHERE date GLOB '??/??/????'
    """)
    conn.execute("""
        UPDATE loan_transactions
        SET date = substr(date,4,2) || '/' || substr(date,1,2) || '/' || substr(date,7)
        WHERE date GLOB '??/??/????'
    """)
    conn.commit()


def _migrate_add_subcategory(conn: sqlite3.Connection) -> None:
    """One-time migration: add subcategory and alias_name columns if absent."""
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(savings_transactions)"
    ).fetchall()]
    if "subcategory" not in cols:
        conn.execute(
            "ALTER TABLE savings_transactions ADD COLUMN subcategory TEXT"
        )
    if "alias_name" not in cols:
        conn.execute(
            "ALTER TABLE savings_transactions ADD COLUMN alias_name TEXT"
        )
    conn.commit()


def _migrate_conversations(conn: sqlite3.Connection) -> None:
    """Create conversations + conversation_messages tables if not present."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def _table_columns(conn: sqlite3.Connection, tbl: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]


def _backfill_txn_ids_for(conn: sqlite3.Connection, tbl: str) -> None:
    """Fill txn_id for rows that still have NULL (legacy rows pre-txn_id column)."""
    extra_col = "reference_number" if tbl == "savings_transactions" else "NULL as reference_number"
    rows = conn.execute(
        f"SELECT rowid, bank, account_name, date, amount, direction, raw_details, {extra_col} "
        f"FROM {tbl} WHERE txn_id IS NULL"
    ).fetchall()
    for r in rows:
        tid = _make_txn_id(dict(r), r["account_name"])
        try:
            conn.execute(f"UPDATE {tbl} SET txn_id=? WHERE rowid=?", (tid, r["rowid"]))
        except sqlite3.IntegrityError:
            conn.execute(f"UPDATE {tbl} SET txn_id=? WHERE rowid=?",
                         (tid + f"_{r['rowid']}", r["rowid"]))
    conn.commit()


# ── Insert ────────────────────────────────────────────────────────────

def upsert_account(account_name: str, bank: str, account_type: str,
                   account_number: str | None = None, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    with conn:
        conn.execute("""
            INSERT INTO accounts (account_name, bank, account_type, account_number)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                bank=excluded.bank, account_type=excluded.account_type,
                account_number=excluded.account_number
        """, (account_name, bank, account_type, account_number))
    conn.close()


def insert_savings_transaction(txn: dict, account_name: str,
                                category: str | None = None,
                                db_path: Path | None = None) -> bool:
    """Returns True if inserted, False if duplicate."""
    conn = _connect(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO savings_transactions
            (txn_id, bank, account_name, account_number, date, date_iso, value_date,
             transaction_type, direction, amount, debit, credit, balance,
             counterparty, counterparty_bank, upi_id, reference_number,
             note, raw_details, alias_name, category)
            VALUES
            (:txn_id, :bank, :account_name, :account_number, :date, :date_iso, :value_date,
             :transaction_type, :direction, :amount, :debit, :credit, :balance,
             :counterparty, :counterparty_bank, :upi_id, :reference_number,
             :note, :raw_details, :alias_name, :category)
        """, {**txn,
              "txn_id":       _make_txn_id(txn, account_name),
              "account_name": account_name,
              "date":         _display_date(txn.get("date", "")),
              "value_date":   _display_date(txn.get("value_date", "")),
              "date_iso":     _normalize_date(txn.get("date", "")),
              "alias_name":   txn.get("alias_name"),
              "category":     category})
        inserted = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        return inserted > 0
    finally:
        conn.close()


def insert_loan_transaction(txn: dict, account_name: str,
                             db_path: Path | None = None) -> bool:
    """Returns True if inserted, False if duplicate."""
    standard = {"bank", "account_number", "date", "value_date",
                "transaction_type", "direction", "amount", "debit",
                "credit", "balance", "raw_details"}
    extra = {k: v for k, v in txn.items() if k not in standard}
    conn = _connect(db_path)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO loan_transactions
            (txn_id, bank, account_name, account_number, date, date_iso, value_date,
             transaction_type, direction, amount, debit, credit, balance,
             extra_data, raw_details)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            _make_txn_id(txn, account_name),
            txn.get("bank"), account_name, txn.get("account_number"),
            _display_date(txn.get("date", "")), _normalize_date(txn.get("date", "")),
            _display_date(txn.get("value_date", "")), txn.get("transaction_type"),
            txn.get("direction"), txn.get("amount"),
            txn.get("debit"), txn.get("credit"), txn.get("balance"),
            json.dumps(extra, default=str), txn.get("raw_details"),
        ))
        inserted = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()
        return inserted > 0
    finally:
        conn.close()


def delete_account_transactions(account_name: str, account_type: str,
                                db_path: Path | None = None) -> None:
    """Delete all transactions for an account (used before force re-import)."""
    conn = _connect(db_path)
    table = "savings_transactions" if account_type == "SAVINGS" else "loan_transactions"
    with conn:
        conn.execute(f"DELETE FROM {table} WHERE account_name=?", (account_name,))
    conn.close()


def log_import(file_hash: str, filename: str, parser: str, account_name: str,
               found: int, inserted: int, duplicates: int,
               db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO import_log
            (file_hash, filename, parser, account_name, found, inserted, duplicates)
            VALUES (?,?,?,?,?,?,?)
        """, (file_hash, filename, parser, account_name, found, inserted, duplicates))
    conn.close()


def is_already_imported(file_hash: str, db_path: Path | None = None) -> bool:
    conn = _connect(db_path)
    row  = conn.execute(
        "SELECT 1 FROM import_log WHERE file_hash=?", (file_hash,)
    ).fetchone()
    conn.close()
    return row is not None


# ── Manual alias / subcategory overrides ─────────────────────────────

def set_alias_for_counterparty(
    counterparty: str,
    alias_name: str | None,
    db_path: Path | None = None,
) -> int:
    """Set alias_name for ALL savings transactions with this raw counterparty.
    Returns number of rows updated."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE savings_transactions SET alias_name=? WHERE counterparty=?",
            (alias_name or None, counterparty)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def set_category_for_counterparty(
    counterparty: str,
    category: str | None,
    db_path: Path | None = None,
) -> int:
    """Set category for ALL savings transactions with this raw counterparty.
    Returns number of rows updated."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE savings_transactions SET category=? WHERE counterparty=?",
            (category or None, counterparty)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def set_subcategory(
    txn_id: str,
    subcategory: str | None,
    db_path: Path | None = None,
) -> bool:
    """Set (or clear) the subcategory override for a savings transaction.
    effective_category = subcategory if set, else category."""
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE savings_transactions SET subcategory=? WHERE txn_id=?",
            (subcategory or None, txn_id)
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


# ── Queries ───────────────────────────────────────────────────────────

def get_accounts(db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM accounts ORDER BY account_type, account_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_savings_balances(db_path: Path | None = None) -> list[dict]:
    """Latest balance row per savings account."""
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT t.account_name, t.bank, t.account_number, t.balance, t.date,
               i.imported_at
        FROM savings_transactions t
        LEFT JOIN import_log i ON i.account_name = t.account_name
        WHERE t.rowid IN (
            SELECT MAX(rowid) FROM savings_transactions
            WHERE date_iso GLOB '????-??-??'
              AND balance IS NOT NULL
            GROUP BY account_name
        )
        GROUP BY t.account_name
        ORDER BY t.account_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_loan_balances(db_path: Path | None = None) -> list[dict]:
    """Latest balance row per loan account, with import date from import_log."""
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT t.account_name, t.bank, t.account_number, t.balance, t.date, t.extra_data,
               i.imported_at
        FROM loan_transactions t
        LEFT JOIN import_log i ON i.account_name = t.account_name
        WHERE (t.account_name, t.date_iso) IN (
            SELECT account_name, MAX(date_iso) FROM loan_transactions GROUP BY account_name
        )
        GROUP BY t.account_name
        ORDER BY t.account_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_transactions(limit: int = 15, db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT txn_id, date, date_iso, account_name, 'SAVINGS' AS account_type,
               direction, transaction_type,
               amount, debit, credit,
               counterparty,
               COALESCE(alias_name, counterparty) AS display_name,
               alias_name,
               category,
               subcategory
        FROM savings_transactions
        WHERE date_iso GLOB '????-??-??'
        UNION ALL
        SELECT txn_id, date, date_iso, account_name, 'LOAN' AS account_type,
               direction, transaction_type,
               amount, debit, credit,
               NULL AS counterparty,
               NULL AS display_name,
               NULL AS alias_name,
               NULL AS category,
               NULL AS subcategory
        FROM loan_transactions
        WHERE date_iso GLOB '????-??-??'
        ORDER BY date_iso DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_spend(months: int = 6, db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT substr(date_iso, 1, 7)                                    AS month,
               SUM(CASE WHEN direction='DEBIT'  THEN debit  ELSE 0 END) AS total_debit,
               SUM(CASE WHEN direction='CREDIT' THEN credit ELSE 0 END) AS total_credit
        FROM savings_transactions
        WHERE date_iso >= date('now', '-' || ? || ' months')
        GROUP BY month
        ORDER BY month DESC
    """, (months,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_merchants(limit: int = 10, db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT counterparty,
               SUM(debit)  AS total_spent,
               COUNT(*)    AS txn_count,
               AVG(debit)  AS avg_per_txn
        FROM savings_transactions
        WHERE direction='DEBIT' AND counterparty IS NOT NULL AND counterparty != ''
        GROUP BY counterparty
        ORDER BY total_spent DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_breakdown(db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT COALESCE(NULLIF(category,''), 'Uncategorized') AS category,
               SUM(debit)  AS total_spent,
               COUNT(*)    AS txn_count
        FROM savings_transactions
        WHERE direction='DEBIT'
        GROUP BY category
        ORDER BY total_spent DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_merchant_transactions(merchant: str, db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("""
        SELECT txn_id, date, account_name, transaction_type, direction,
               debit, credit, upi_id, counterparty_bank
        FROM savings_transactions
        WHERE counterparty LIKE ?
        ORDER BY date_iso DESC
    """, (f"%{merchant}%",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_transactions(account_type: str | None = None,
                         direction: str | None = None,
                         search: str | None = None,
                         limit: int = 1000,
                         db_path: Path | None = None) -> list[dict]:
    conn   = _connect(db_path)
    parts  = []
    params = []

    if account_type != "LOAN":
        w, p = _build_savings_where(direction, search)
        parts.append(f"""
            SELECT txn_id, date, date_iso, bank, account_name, 'SAVINGS' AS account_type,
                   transaction_type, direction,
                   COALESCE(debit,0) AS debit, COALESCE(credit,0) AS credit,
                   balance, counterparty, alias_name,
                   COALESCE(alias_name, counterparty) AS display_name,
                   category, subcategory,
                   COALESCE(subcategory, category) AS effective_category
            FROM savings_transactions {w}
        """)
        params.extend(p)

    if account_type != "SAVINGS":
        w, p = _build_loan_where(direction, search)
        parts.append(f"""
            SELECT txn_id, date, date_iso, bank, account_name, 'LOAN' AS account_type,
                   transaction_type, direction,
                   COALESCE(debit,0) AS debit, COALESCE(credit,0) AS credit,
                   balance, NULL AS counterparty, NULL AS alias_name,
                   NULL AS display_name, NULL AS category,
                   NULL AS subcategory, NULL AS effective_category
            FROM loan_transactions {w}
        """)
        params.extend(p)

    if not parts:
        return []

    sql  = " UNION ALL ".join(parts) + " ORDER BY date_iso DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_import_log(db_path: Path | None = None) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM import_log ORDER BY imported_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────

def _build_savings_where(direction, search) -> tuple[str, list]:
    clauses, params = [], []
    if direction:
        clauses.append("direction = ?")
        params.append(direction)
    if search:
        clauses.append("(counterparty LIKE ? OR transaction_type LIKE ? OR bank LIKE ? OR date LIKE ? OR account_name LIKE ?)")
        params.extend([f"%{search}%"] * 5)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _build_loan_where(direction, search) -> tuple[str, list]:
    clauses, params = [], []
    if direction:
        clauses.append("direction = ?")
        params.append(direction)
    if search:
        clauses.append("(transaction_type LIKE ? OR bank LIKE ? OR date LIKE ? OR account_name LIKE ?)")
        params.extend([f"%{search}%"] * 4)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ── Conversation persistence ──────────────────────────────────────────

def create_conversation(db_path: Path | None = None) -> int:
    """Create a new conversation row and return its id."""
    conn = _connect(db_path)
    try:
        cur = conn.execute("INSERT INTO conversations DEFAULT VALUES")
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_last_conversation_id(db_path: Path | None = None) -> int | None:
    """Return the id of the most recent conversation, or None if none exist."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT MAX(id) FROM conversations").fetchone()
        return row[0] if row and row[0] is not None else None
    finally:
        conn.close()


def save_message(conversation_id: int, role: str, content: str,
                 db_path: Path | None = None) -> None:
    """Append a message to an existing conversation."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )
        conn.commit()
    finally:
        conn.close()


def get_conversation_messages(conversation_id: int,
                              db_path: Path | None = None) -> list[dict]:
    """Return all messages for a conversation in insertion order."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM conversation_messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
