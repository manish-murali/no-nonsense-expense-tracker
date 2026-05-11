# Technical Reference

For developers who want to understand the codebase, extend it, or add support
for a new bank.

---

## Table of Contents

  1. Project Structure
  2. Database Schema
  3. Supported Banks & Parsers
  4. AI Pipeline
  5. Configuration Files
  6. How to Add a New Bank Parser
  7. Dependencies
  8. Error Codes


---


## 1. Project Structure

    expense-tracker/
    ├── app.py                   Entry point — launches the Textual TUI
    ├── cli.py                   Command-line interface
    ├── importer.py              PDF → parse → deduplicate → store pipeline
    ├── categorizer.py           Pattern-matching auto-categorisation engine
    ├── display_name.py          Display name load / apply / save logic
    ├── errors.py                Centralised error definitions (AppError + codes)
    │
    ├── parsers/
    │   ├── __init__.py          PARSER_REGISTRY dict
    │   ├── base.py              Shared utilities (parse_amount, pdfplumber helpers)
    │   ├── sbi_savings.py       SBI Savings parser
    │   ├── axis_savings.py      Axis Bank Savings parser
    │   ├── sbi_loan.py          SBI Gold Loan parser
    │   └── cbi_loan.py          CBI Education Loan parser
    │
    ├── storage/
    │   └── db.py                All SQLite operations (schema, migrations, queries)
    │
    ├── ai/
    │   ├── __init__.py          Exports AIAgent + exceptions
    │   ├── agent.py             Two-step LLM pipeline + conversation history
    │   └── prompts/
    │       ├── system.txt       Role and rules for the answer step
    │       ├── sql_gen.txt      Schema-grounded SQL generation template
    │       └── answer.txt       Result → natural-language answer template
    │
    ├── ui/
    │   ├── app.py               Textual App, CSS, keybindings, theme toggle
    │   ├── widgets.py           Card widget (theme-aware)
    │   └── screens/
    │       ├── overview.py      Overview tab (balances, chart, recent txns)
    │       ├── expenses.py      Expenses & Trends tab
    │       ├── ask.py           Ask AI tab
    │       └── transaction_log.py  Transaction Log tab
    │
    ├── docs/                    This documentation folder
    ├── statements/              PDF storage (gitignored)
    ├── config.json              Account configuration (gitignored)
    ├── tracker.db               SQLite database (gitignored)
    ├── categories.json          Category rules (gitignored)
    ├── display_name.json        Display name mappings (gitignored)
    ├── ai_config.json           AI model config (gitignored)
    └── ai_config.example.json   Template for ai_config.json (committed)


---


## 2. Database Schema

All data is stored in a single SQLite file: `tracker.db`


### savings_transactions

    Column            Type    Notes
    ────────────────────────────────────────────────────────────────────
    txn_id            TEXT    Primary key — SHA256 of raw_details (first 32 chars)
    bank              TEXT    e.g. 'SBI', 'AXIS'
    account_name      TEXT    e.g. 'SBI Savings'
    account_number    TEXT
    date              TEXT    Display format: DD/MM/YYYY
    date_iso          TEXT    Sortable format: YYYY-MM-DD (indexed)
    value_date        TEXT    DD/MM/YYYY
    transaction_type  TEXT    UPI, NEFT, IMPS, ATM_CHARGE, INTEREST, etc.
    direction         TEXT    'CREDIT' or 'DEBIT'
    amount            REAL
    debit             REAL    Amount if DEBIT, else 0
    credit            REAL    Amount if CREDIT, else 0
    balance           REAL    Running balance after this transaction
    counterparty      TEXT    Raw merchant/person name from bank
    counterparty_bank TEXT
    upi_id            TEXT
    reference_number  TEXT
    note              TEXT    Parsed description from raw_details
    raw_details       TEXT    Full unparsed string from bank statement
    display_name      TEXT    User-set clean name (NULL if not set)
    category          TEXT    Auto-assigned from categories.json rules
    tag               TEXT    Manual per-transaction override (NULL if not set)
    imported_at       TEXT    datetime('now') at import time


### loan_transactions

Similar to `savings_transactions`.
No `counterparty`, `display_name`, `category`, or `tag` columns.
Has `extra_data TEXT` (JSON blob) for bank-specific loan metadata.


### accounts

    account_name    TEXT UNIQUE
    bank            TEXT
    account_type    TEXT    'SAVINGS' or 'LOAN'
    account_number  TEXT
    created_at      TEXT


### import_log

    file_hash    TEXT UNIQUE   SHA256 of the PDF file (duplicate detection key)
    filename     TEXT
    parser       TEXT
    account_name TEXT
    imported_at  TEXT
    found        INTEGER       Total rows parsed from PDF
    inserted     INTEGER       New rows stored
    duplicates   INTEGER       Rows already present in DB


### conversations / conversation_messages

Used by the Ask AI tab to persist chat history across sessions.

    conversations:
      id           INTEGER PRIMARY KEY AUTOINCREMENT
      created_at   TEXT

    conversation_messages:
      id              INTEGER PRIMARY KEY AUTOINCREMENT
      conversation_id INTEGER  FK → conversations.id (CASCADE DELETE)
      role            TEXT     'user' | 'assistant' | 'sql'
      content         TEXT
      created_at      TEXT


### Indexes

    idx_sav_date   savings_transactions(date_iso)
    idx_sav_dir    savings_transactions(direction)
    idx_sav_cat    savings_transactions(category)
    idx_sav_acct   savings_transactions(account_name)
    idx_loan_date  loan_transactions(date_iso)
    idx_loan_acct  loan_transactions(account_name)


### Migrations

`db.init_db()` runs a set of idempotent migration functions on every startup:

  - `_migrate_drop_id`      Removes legacy `id` column, promotes `txn_id` to sole PK
  - `_migrate_date_format`  Flips MM/DD/YYYY → DD/MM/YYYY (one-time, detects by day > 12)
  - `_migrate_add_tag`      Renames `subcategory` → `tag`, `alias_name` → `display_name`
  - `_migrate_conversations` Creates conversation tables if absent


---


## 3. Supported Banks & Parsers

Each parser is a Python function registered in `parsers/__init__.py`:

    PARSER_REGISTRY = {
        "sbi_savings":  {"func": ..., "bank": "SBI",  "account_type": "SAVINGS"},
        "axis_savings": {"func": ..., "bank": "AXIS", "account_type": "SAVINGS"},
        "sbi_loan":     {"func": ..., "bank": "SBI",  "account_type": "LOAN"},
        "cbi_loan":     {"func": ..., "bank": "CBI",  "account_type": "LOAN"},
    }


### Fields produced by all parsers

    bank, account_type, date, value_date, transaction_type, direction,
    amount, debit, credit, balance, counterparty, counterparty_bank,
    upi_id, reference_number, note, raw_details


### Parser detail

**sbi_savings.py**
  - Columns: Date, Details, Ref No, Debit, Credit, Balance
  - Transaction types: UPI CR/DR, NEFT, RTGS, IMPS, ATM_CHARGE, INTEREST, ACH
  - Direction: from UPI direction tag in details string, or from debit/credit column

**axis_savings.py**
  - Columns: Date, Transaction Details, Chq, Withdrawal, Deposit, Balance
  - Transaction types: IMPS/P2A, NEFT (slash-delimited inward), UPI CR/DR, RTGS,
    ATM_CHARGE, INTEREST, CHARGE
  - Direction: Withdrawal column → DEBIT, Deposit column → CREDIT

**sbi_loan.py**
  - Columns: Post Date, Details, Ref No, Debit, Credit, Balance
  - Transaction types: PRINCIPAL_REPAYMENT, INTEREST_REPAYMENT, COMPOUND_REPAYMENT
  - Also extracts: sanctioned amount, outstanding balance, interest rate, tenure

**cbi_loan.py**
  - Columns: Post Date, Details, Ref No, Debit, Credit, Balance
  - Transaction types: INTEREST_CHARGE, PRINCIPAL_REPAYMENT, DISBURSEMENT,
    PENAL_INTEREST, CHARGE
  - Direction: trailing "DR"/"CR" indicator in balance column


---


## 4. AI Pipeline


### Architecture

    User question
        ↓
    Step 1 — SQL Generation
        Messages: [system = sql_gen.txt] + [sql_history (last 10)] + [user question]
        POST /api/chat → Ollama (gemma3:4b)
        Extract SELECT from response
        Validate: must start with SELECT; blocklist: INSERT/UPDATE/DELETE/DROP/etc.
        PRAGMA query_only = ON (SQLite engine-level write guard)
        Execute against tracker.db → rows
        ↓
    Step 2 — Answer Generation
        Messages: [system = answer.txt] + [chat_history (last 10)] + [question + JSON rows]
        POST /api/chat → Ollama
        Return plain-English answer
        ↓
    Persist to DB
        conversation_messages: role=user, role=sql, role=assistant


### sql_gen.txt prompt structure

  - Role definition (SQLite query generator)
  - Full schema: savings_transactions (all columns), loan_transactions, accounts
  - 16 query rules: date filtering, LOWER() for case-insensitive LIKE, OR+AND
    parentheses, "last N months" → date('now', '-N months'), etc.
  - DB context injected at runtime: date range, accounts, top counterparties
  - 11 worked example Q→SQL pairs
  - `{question}` placeholder at the end


### Safety layers

    1. Keyword blocklist regex:  INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA
    2. Response must start with SELECT
    3. SQLite PRAGMA query_only = ON  — engine refuses writes even if blocklist is bypassed
    4. Results capped: fetchmany(50); only 15 rows sent to answer prompt


### Conversation history

Two separate in-memory lists (both capped at 10 messages / 5 turns):

    _sql_history:
      [{"role": "user",      "content": "<question>"},
       {"role": "assistant", "content": "<sql>"},  ...]

    _chat_history:
      [{"role": "user",      "content": "<question>"},
       {"role": "assistant", "content": "<answer>"}, ...]

Both are persisted to `tracker.db` in `conversation_messages`.
On startup: last `conversation_id` is loaded from DB, histories are rebuilt,
and the chat log is replayed in the UI.
On Clear: a new conversation row is created, both histories reset in memory.


### Configuration (ai_config.json)

    {
      "model":       "gemma3:4b",
      "endpoint":    "http://localhost:11434",
      "temperature": 0.1,
      "timeout":     60
    }

`ai_config.json` is optional — defaults are used if absent.
It is gitignored so model preferences stay private per machine.


---


## 5. Configuration Files


### config.json (gitignored)

    [
      {
        "account_name": "SBI Savings",       Display name shown in the app
        "parser":       "sbi_savings",       Must match a key in PARSER_REGISTRY
        "folder":       "statements/sbi_savings",  Relative path to PDF folder
        "password":     "yourpassword"       PDF password, or null if none
      }
    ]


### categories.json (gitignored)

    {
      "Zomato":   "Food & Dining",
      "Netflix":  "Subscriptions",
      "Airtel":   "Telecom"
    }

Pattern matching is case-insensitive substring search.
The app ships with 18 built-in defaults; users add more via CLI or UI.
Running `python cli.py category apply` re-applies all rules to existing transactions.


### display_name.json (gitignored)

    {
      "IRCTCTOU":  "IRCTC",
      "JD":  "John Doe"
    }

Applied at import time via `apply_alias(counterparty)`.
If the display name differs from the raw name, the `display_name` column is set in the DB.
The raw `counterparty` value is always preserved unchanged.


### ai_config.json (gitignored)

Copy from `ai_config.example.json`. All fields are optional — defaults work out of the box.


### .gitignore summary

    tracker.db, tracker.db-shm, tracker.db-wal
    config.json, categories.json, display_name.json, aliases.json, ai_config.json
    statements/**/*.pdf, data/**/*.pdf
    __pycache__/, *.pyc, .venv/, venv/


---


## 6. How to Add a New Bank Parser

**Step 1 — Create `parsers/yourbank_savings.py`**

Implement a function with this signature:

    def load_statement(pdf_path, password=None, account_number=None) -> list[dict]:

Each dict in the returned list must contain at minimum:

    bank, date, transaction_type, direction, debit, credit, balance, raw_details

Optional fields: `counterparty`, `counterparty_bank`, `upi_id`, `reference_number`, `note`

Refer to `parsers/base.py` for shared utilities:
  - `extract_tables_from_pdf(pdf_path, password)` → list of rows
  - `find_header_row(rows, keywords)` → index of header row
  - `col_index(header, candidates)` → column index by keyword matching
  - `parse_amount(text)` → float or None


**Step 2 — Register the parser in `parsers/__init__.py`**

    from parsers.yourbank_savings import load_statement as yourbank_load

    PARSER_REGISTRY["yourbank_savings"] = {
        "func":         yourbank_load,
        "bank":         "YOURBANK",
        "account_type": "SAVINGS",
    }


**Step 3 — Add an entry to `config.json`**

    {
      "account_name": "Your Bank Savings",
      "parser":       "yourbank_savings",
      "folder":       "statements/yourbank_savings",
      "password":     null
    }


**Step 4 — Test**

    python cli.py import --file statements/yourbank_savings/statement.pdf \
                         --parser yourbank_savings \
                         --account-name "Your Bank Savings"


---


## 7. Dependencies

### Python packages

    pdfplumber      Extracts tables from PDF bank statements
    textual         Terminal UI framework — https://textual.textualize.io
    httpx           Async HTTP client for Ollama API calls

Install all with:

    pip install -r requirements.txt


### External tools

    Ollama          Local LLM runtime — https://ollama.com
                    Required only for the Ask AI tab.
                    Default model: gemma3:4b (~2.5 GB download)

    SQLite          Built into Python's standard library — no installation needed.


---


## 8. Error Codes

    Code      Meaning
    ────────────────────────────────────────────────────────
    PDF_001   Wrong PDF password
    PDF_002   PDF file not found
    PDF_003   No transactions found in PDF
    PDF_004   Unknown / unsupported parser name
    PDF_005   Could not find header row in PDF tables
    CFG_001   config.json file not found
    CFG_002   Password not configured for this account
    CFG_003   Statement folder path does not exist
    DB_001    Database insert failed
    DB_002    Database migration failed


---

← [User Manual](user-manual.md) · [Back to README](../README.md)
