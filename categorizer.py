"""
Rule-based transaction categorizer.
Rules are stored in categories.json (gitignored) and matched against
counterparty and raw_details fields via case-insensitive substring match.

Manage rules via CLI:
    python cli.py category add --pattern "Zomato" --category "Food & Dining"
    python cli.py category list
    python cli.py category apply
"""

import json
import sqlite3
from pathlib import Path

CATEGORIES_FILE = Path(__file__).parent / "categories.json"

DEFAULT_RULES: dict[str, str] = {
    "Zomato":    "Food & Dining",
    "Swiggy":    "Food & Dining",
    "Blinkit":   "Groceries",
    "BigBasket": "Groceries",
    "Dunzo":     "Groceries",
    "Netflix":   "Subscriptions",
    "Spotify":   "Subscriptions",
    "Hotstar":   "Subscriptions",
    "Amazon":    "Shopping",
    "Flipkart":  "Shopping",
    "Myntra":    "Shopping",
    "Airtel":    "Telecom",
    "BSNL":      "Telecom",
    "Jio":       "Telecom",
    "CRED":      "Credit Card",
    "HDFC CC":   "Credit Card",
    "ATM":       "ATM Withdrawal",
    "INTEREST":  "Interest",
    "IRCTC":     "Travel",
    "OLA":       "Transport",
    "UBER":      "Transport",
}


def _load() -> dict[str, str]:
    """Load categories.json, creating it with defaults if it doesn't exist."""
    if not CATEGORIES_FILE.exists():
        _save(DEFAULT_RULES)
    with open(CATEGORIES_FILE) as f:
        return json.load(f)


def _save(rules: dict[str, str]) -> None:
    """Write rules to categories.json, sorted by pattern for readability."""
    CATEGORIES_FILE.write_text(
        json.dumps(dict(sorted(rules.items())), indent=2, ensure_ascii=False)
    )


def add_rule(pattern: str, category: str) -> None:
    """Add or update a pattern → category rule in categories.json."""
    rules = _load()
    rules[pattern] = category
    _save(rules)


def get_rules() -> dict[str, str]:
    """Return all rules as {pattern: category}."""
    return _load()


def categorize(txn: dict, db_path: Path | None = None) -> str:
    """Return a category for a single transaction dict."""
    rules = _load()
    haystack = " ".join(filter(None, [
        txn.get("counterparty") or "",
        txn.get("raw_details")  or "",
    ])).lower()
    for pattern, category in rules.items():
        if pattern.lower() in haystack:
            return category
    return "Uncategorized"


def recategorize_all(db_path: Path | None = None) -> int:
    """
    Re-apply all rules from categories.json to every savings transaction.
    Overwrites existing categories. Returns number of rows updated.
    """
    from storage import get_db_path
    rules   = _load()
    db_file = db_path or get_db_path()
    conn    = sqlite3.connect(db_file)
    total   = 0
    try:
        for pattern, category in rules.items():
            like = f"%{pattern}%"
            cur  = conn.execute("""
                UPDATE savings_transactions
                SET category = ?
                WHERE counterparty LIKE ? OR raw_details LIKE ?
            """, (category, like, like))
            total += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return total


# Keep seed_defaults as a no-op shim so existing call sites don't break
def seed_defaults(db_path: Path | None = None) -> None:
    """Ensure categories.json exists with at least the default rules."""
    _load()  # creates the file with defaults if missing
