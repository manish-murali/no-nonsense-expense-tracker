# Personal Expense Tracker

A private, local-first personal finance tool that reads your bank statements (PDF),
organises all your transactions, and lets you ask questions about your money in plain
English — without sending any data to the cloud.

Everything runs on your own computer. Your bank data never leaves your machine.

---


## Table of Contents

  1.  What This App Does
  2.  Key Features
  3.  Screenshots & Interface Overview
  4.  Getting Started (Setup Guide)
  5.  How to Import Bank Statements
  6.  Using the App — Tab by Tab
  7.  Categorising Your Spending
  8.  Aliases — Clean Up Merchant Names
  9.  Ask AI — Chat With Your Data
  10. Keyboard Shortcuts
  11. Command-Line Reference
  12. ─────────────────────────────────────
  13. Technical Reference (Developers)
  14. Project Structure
  15. Database Schema
  16. Supported Banks & Parsers
  17. AI Pipeline
  18. Configuration Files
  19. How to Add a New Bank Parser
  20. Dependencies


---


## 1. What This App Does

Most people have no idea where their money goes each month. Bank apps show raw
transactions with ugly merchant codes like "IRCTCTOU" or "POS 441892 ZOMATO". They
don't categorise, search, or explain anything.

This app fixes that. You drop your bank statement PDFs into a folder, run one command,
and within seconds every transaction is:

  - Parsed and stored in a local database
  - Automatically categorised (Food, Transport, Salary, etc.)
  - Given a clean, readable merchant name
  - Searchable and filterable in a visual interface
  - Queryable in plain English ("How much did I spend on Zomato last month?")

No subscription. No cloud. No sharing your financial data with anyone.


---


## 2. Key Features


### Automatic Bank Statement Import
Drop your PDF bank statements into a folder and the app reads them automatically.
It handles password-protected PDFs, skips files it has already imported (no duplicates),
and supports multiple accounts at the same time.

Currently supported banks: SBI , Axis, CBI.


### Smart Auto-Categorisation
Every transaction is automatically assigned a category based on who you paid.
Zomato becomes "Food & Dining". Netflix becomes "Subscriptions". Airtel becomes "Telecom".
You can add your own rules and change any category at any time.


### Clean Merchant Names (Aliases)
Banks display ugly codes like "IRCTCTOU" or "OGS (INDIA) PVT LTD (G3-ITP-".
The alias system lets you replace these with readable names like "IRCTC" or "Optum".
Once set, the clean name shows everywhere and future imports use it automatically.


### Interactive Dashboard (Overview Tab)
See all your account balances on one screen, a bar chart of spending vs income
for the last 3 months, and your 25 most recent transactions — all at a glance.


### Spending Trends (Expenses & Trends Tab)
A visual breakdown of your spending by category with bar charts.
Click any merchant to see every transaction you've had with them.


### Full Transaction Log
Browse all 600+ transactions with search and filter. Filter by Credits, Debits,
Savings accounts, or Loans. Search by merchant name, date, or transaction type.
Click any Alias, Category, or Subcategory cell to edit it directly.


### Per-Transaction Subcategory
If the automatic category isn't specific enough, you can set a Subcategory on any
individual transaction. Example: Category = "Shopping", Subcategory = "Birthday gift".
Subcategories only change that one transaction — not all of them.


### Ask AI (Local, Private)
Ask questions about your money in plain English and get answers in plain English.
"How much did I spend on Zomato?" → "You spent ₹2,345 on Zomato across 12 transactions."
The AI runs entirely on your computer using Ollama. Your data never leaves your machine.
The conversation is remembered between sessions.


### Dark Mode / Light Mode
Toggle between dark and light themes any time with the T key.


### 100% Private and Local
No accounts. No internet required (except to download Ollama once).
All data lives in a single SQLite file (tracker.db) on your computer.


---


## 3. Interface Overview

The app has four tabs, switchable with keyboard keys 1 through 4:

  [1] Overview          — Balances, monthly chart, recent transactions
  [2] Expenses & Trends — Category breakdown, top merchants, transaction detail
  [3] Ask AI            — Chat with your transaction data
  [4] Transaction Log   — Full searchable, editable transaction table

Navigation:
  - Press 1, 2, 3, or 4 to switch tabs instantly
  - Press T to toggle dark/light theme
  - Press Ctrl+R to refresh all data
  - Press Q to quit


---


## 4. Getting Started (Setup Guide)

Follow these steps to get the app running for the first time.


### Step 1 — Check Python is installed

Open a terminal and run:

    python --version

You need Python 3.11 or newer. If you don't have it, download it from python.org.


### Step 2 — Download the project

If you received this as a folder, skip this step.
If you're cloning from GitHub:

    git clone https://github.com/your-username/expense-tracker.git
    cd expense-tracker


### Step 3 — Install dependencies

    pip install -r requirements.txt

This installs three libraries: pdfplumber (reads PDFs), textual (the visual interface),
and httpx (for AI communication).


### Step 4 — Create your account configuration

Create a file called config.json in the project folder. This tells the app which bank
accounts you have and where to find their statements.

Example config.json:

    [
      {
        "account_name": "SBI Savings",
        "parser":       "sbi_savings",
        "folder":       "statements/sbi_savings",
        "password":     "your_pdf_password"
      },
      {
        "account_name": "Axis Savings",
        "parser":       "axis_savings",
        "folder":       "statements/axis_savings",
        "password":     "your_pdf_password"
      }
    ]

Available parser values (one per bank type):
  - sbi_savings    — SBI savings/current account statements
  - axis_savings   — Axis Bank savings account statements
  - sbi_loan       — SBI Gold Loan statements
  - cbi_loan       — CBI Education Loan statements

If your PDF has no password, use:  "password": null


### Step 5 — Create statement folders

Create a folder called statements/ in the project directory, then one subfolder
per account (matching the folder paths in config.json):

    statements/
      sbi_savings/
      axis_savings/

Drop your PDF bank statements into the matching folder.


### Step 6 — Launch the app

    python app.py

The app will automatically import any new PDFs it finds on startup.


### Step 7 — Set up AI (optional)

To use the Ask AI tab, you need Ollama installed:

    # Install Ollama (macOS)
    brew install ollama

    # Start Ollama (keep this terminal open)
    ollama serve

    # Pull the AI model (one-time, ~2.5 GB download)
    ollama pull gemma3:4b

    # Optional: start Ollama automatically on login
    brew services start ollama

Once Ollama is running, reopen the app. The Ask AI tab will connect automatically.


---


## 5. How to Import Bank Statements


### Automatic import (recommended)

Just drop PDF files into the correct statements/ subfolder and launch the app.
It imports everything automatically on startup and shows a notification with how
many new transactions were added.


### Manual import via command line

Import a single file:

    python cli.py import \
      --file statements/sbi_savings/mystatement.pdf \
      --parser sbi_savings \
      --account-name "SBI Savings" \
      --password yourpassword

Import all configured accounts at once:

    python cli.py import-all

Force re-import (overwrites existing data for that account):

    python cli.py import-all --force


### Duplicate detection

The app tracks every PDF by a unique fingerprint. If you import the same file twice,
it is skipped automatically. No duplicates will appear.


---


## 6. Using the App — Tab by Tab


### Overview Tab (press 1)

Shows three sections:

  ACCOUNT BALANCES
  One card per savings account showing the current balance and the date of the
  last statement imported. A "Total Savings" card shows the combined balance.
  Loan accounts appear below in red, showing what you still owe.

  MONTHLY SPEND CHART
  A simple bar chart comparing expenses (red bars) and income (green bars)
  for the last 3 months. The longest bar represents the highest value.

  RECENT TRANSACTIONS
  The 25 most recent transactions across all accounts.
  Columns: Date, Account, Direction (↑ IN / ↓ OUT), Type, Amount, Counterparty,
           Alias, Category, Subcategory.
  Click any Alias, Category, or Subcategory cell to edit it directly.


### Expenses & Trends Tab (press 2)

  SPENDING BY CATEGORY
  A bar chart of your total spending broken down by category.
  Longer bar = more money spent in that category.

  TOP 10 MERCHANTS
  A table of the merchants where you spend the most, showing:
  total spent, number of transactions, and average per transaction.

  MERCHANT DETAIL
  Click any merchant row to see every individual transaction with that merchant.


### Ask AI Tab (press 3)

Type any question about your finances in plain English and press Enter or Send.

Examples:
  - What is my current balance?
  - How much did I spend on Zomato?
  - What are my biggest expenses this month?
  - Compare my spending in February vs March
  - How much loan do I still owe?
  - What is my monthly salary?

The AI shows the query it ran (in small text at the bottom) so you can verify
what data it fetched. Press Clear to start a new conversation.

Note: Ollama must be running for this tab to work. See Step 7 in the setup guide.


### Transaction Log Tab (press 4)

A complete, searchable view of every transaction.

  SEARCH
  Type in the search box to filter by merchant name, account, date, or type.
  Results update live as you type.

  FILTER BUTTONS
  All | Credits | Debits | Savings | Loans
  Click to filter the entire table by transaction direction or account type.

  EDITING
  Click any cell in the Alias, Category, or Subcategory column to edit it.
  The edit panel at the bottom activates with the appropriate input.

  - Alias edit:       Updates ALL transactions with the same counterparty + saves to aliases.json
  - Category edit:    Updates ALL transactions with the same counterparty + saves to categories.json
  - Subcategory edit: Updates ONLY that single transaction

  Press Save to apply, Clear to remove.


---


## 7. Categorising Your Spending

Categories are assigned automatically when you import a statement.
The app matches the merchant name against a list of rules (stored in categories.json).


### View existing categories

    python cli.py category list


### Add a new category rule

    python cli.py category add --pattern "BookMyShow" --category "Entertainment"

This saves the rule and immediately applies it to all matching existing transactions.


### Apply all rules to existing transactions

    python cli.py category apply

Useful after adding many new rules at once.


### Edit from the UI

In either the Transaction Log or the Overview Recent Transactions table:
  1. Click a cell in the Category column
  2. Type the category name in the edit panel
  3. Press Save

This updates all transactions from the same merchant and saves the rule.


### Built-in categories (examples)

  Food & Dining   — Zomato, Swiggy
  Groceries       — Blinkit, BigBasket, Dunzo
  Shopping        — Amazon, Flipkart, Myntra
  Subscriptions   — Netflix, Spotify, Hotstar
  Telecom         — Airtel, Jio, BSNL
  Transport       — Ola, Uber
  Travel          — IRCTC
  Credit Card     — CRED, HDFC CC
  ATM Withdrawal  — ATM transactions
  Interest        — Bank interest credits


---


## 8. Aliases — Clean Up Merchant Names

Banks use raw transaction codes that are hard to read.
Aliases let you replace these with human-readable names.

Example: "OGS (INDIA) PVT LTD (G3-ITP-" → "Optum"

The raw name from the bank is always preserved in the database.
The alias is shown in the Alias column everywhere in the app.


### Add an alias via command line

    python cli.py alias add --counterparty "IRCTCTOU" --alias "IRCTC"


### List existing aliases

    python cli.py alias list


### Add or edit an alias from the UI

In the Transaction Log or Overview table:
  1. Click a cell in the Alias column
  2. Type the clean name
  3. Press Save

All transactions from the same merchant are updated immediately.
Press Clear to remove an alias.


---


## 9. Ask AI — Chat With Your Data

The AI assistant understands your transaction database and answers questions in plain
English. It is powered by Ollama, a tool that runs AI models locally on your computer.


### How it works (non-technical summary)

When you ask a question, the AI does two things:

  1. It figures out what data to fetch from your transactions
     (based on your question, account history, and merchant names)

  2. It turns that data into a human-readable answer
     (in ₹ amounts, DD/MM/YYYY dates, plain sentences)

The small line at the bottom of the chat labelled "SQL →" shows exactly what it
fetched — you can verify the AI is looking at the right data.


### Tips for better results

  - Be specific: "How much did I spend on Zomato last month?" works better than
    "Zomato?"

  - Use follow-up questions: "What about February?" after asking about March
    — the AI remembers the context.

  - If you get a wrong answer, press Clear and rephrase the question.

  - The AI knows your account names, top merchants, and date range automatically.


### Conversation memory

Conversations are saved between sessions. When you reopen the app, the last
conversation is restored. Press Clear to start fresh (old conversations are kept
in the database, not deleted).


### AI model options

The default model is gemma3:4b. You can switch to a different model by creating
ai_config.json (copy from ai_config.example.json) and changing the model name.

Alternatives:
  - gemma3:12b    — Better answers, needs more RAM
  - llama3.2:3b  — Faster, slightly less accurate
  - phi4-mini    — Good at reasoning, compact size


---


## 10. Keyboard Shortcuts

  Key         Action
  ─────────────────────────────────────────
  1           Switch to Overview tab
  2           Switch to Expenses & Trends tab
  3           Switch to Ask AI tab
  4           Switch to Transaction Log tab
  T           Toggle dark / light theme
  Ctrl+R      Refresh all data
  Q           Quit the app
  Enter       Submit in Ask AI chat input


---


## 11. Command-Line Reference

The app can also be controlled from the terminal without opening the visual interface.

    # Show help
    python cli.py --help

    # Import a single statement
    python cli.py import --file PATH --parser PARSER --account-name NAME [--password PASS] [--force]

    # Import all configured accounts
    python cli.py import-all [--config config.json] [--force]

    # List registered accounts
    python cli.py accounts

    # Print a summary (balances, monthly spend, top merchants)
    python cli.py summary

    # Category management
    python cli.py category list
    python cli.py category add --pattern "TEXT" --category "CATEGORY NAME"
    python cli.py category apply

    # Alias management
    python cli.py alias list
    python cli.py alias add --counterparty "RAW NAME" --alias "CLEAN NAME"


---
---


## 12. Technical Reference (Developers)

The sections below are intended for developers who want to understand the codebase,
extend it, or contribute to it.


---


## 13. Project Structure

    expense-tracker/
    ├── app.py                  Entry point — launches the Textual TUI
    ├── cli.py                  Command-line interface
    ├── importer.py             PDF → parse → deduplicate → store pipeline
    ├── categorizer.py          Pattern-matching auto-categorisation engine
    ├── aliases.py              Alias load / apply / save logic
    ├── errors.py               Centralised error definitions (AppError + codes)
    │
    ├── parsers/
    │   ├── __init__.py         PARSER_REGISTRY dict
    │   ├── base.py             Shared utilities (parse_amount, pdfplumber helpers)
    │   ├── sbi_savings.py      SBI Savings parser
    │   ├── axis_savings.py     Axis Bank Savings parser
    │   ├── sbi_loan.py         SBI Gold Loan parser
    │   └── cbi_loan.py         CBI Education Loan parser
    │
    ├── storage/
    │   └── db.py               All SQLite operations (schema, migrations, queries)
    │
    ├── ai/
    │   ├── __init__.py         Exports AIAgent + exceptions
    │   ├── agent.py            Two-step LLM pipeline + conversation history
    │   └── prompts/
    │       ├── system.txt      Role and rules for the answer step
    │       ├── sql_gen.txt     Schema-grounded SQL generation template
    │       └── answer.txt      Result → natural-language answer template
    │
    ├── ui/
    │   ├── app.py              Textual App, CSS, keybindings, theme toggle
    │   ├── widgets.py          Card widget (theme-aware)
    │   └── screens/
    │       ├── overview.py     Overview tab (balances, chart, recent txns)
    │       ├── expenses.py     Expenses & Trends tab
    │       ├── ask.py          Ask AI tab
    │       └── transaction_log.py  Transaction Log tab
    │
    ├── statements/             PDF storage (gitignored)
    ├── config.json             Account configuration (gitignored)
    ├── tracker.db              SQLite database (gitignored)
    ├── categories.json         Category rules (gitignored)
    ├── aliases.json            Alias mappings (gitignored)
    ├── ai_config.json          AI model config (gitignored)
    └── ai_config.example.json  Template for ai_config.json (committed)


---


## 14. Database Schema

All data is stored in a single SQLite file: tracker.db

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
    alias_name        TEXT    User-set clean name (NULL if not set)
    category          TEXT    Auto-assigned from categories.json rules
    subcategory       TEXT    Manual per-transaction override (NULL if not set)
    imported_at       TEXT    datetime('now') at import time

### loan_transactions

    Similar to savings_transactions.
    No counterparty, alias_name, category, subcategory columns.
    Has extra_data TEXT (JSON) for bank-specific loan metadata.

### accounts

    account_name    TEXT UNIQUE
    bank            TEXT
    account_type    TEXT    'SAVINGS' or 'LOAN'
    account_number  TEXT
    created_at      TEXT

### import_log

    file_hash    TEXT UNIQUE   SHA256 of the PDF file
    filename     TEXT
    parser       TEXT
    account_name TEXT
    imported_at  TEXT
    found        INTEGER
    inserted     INTEGER
    duplicates   INTEGER

### conversations / conversation_messages

    conversations:
      id           INTEGER PRIMARY KEY AUTOINCREMENT
      created_at   TEXT

    conversation_messages:
      id              INTEGER PRIMARY KEY AUTOINCREMENT
      conversation_id INTEGER (FK → conversations.id)
      role            TEXT    'user' | 'assistant' | 'sql'
      content         TEXT
      created_at      TEXT

### Indexes

    idx_sav_date   savings_transactions(date_iso)
    idx_sav_dir    savings_transactions(direction)
    idx_sav_cat    savings_transactions(category)
    idx_sav_acct   savings_transactions(account_name)
    idx_loan_date  loan_transactions(date_iso)
    idx_loan_acct  loan_transactions(account_name)


---


## 15. Supported Banks & Parsers

Each parser is a Python function registered in parsers/__init__.py:

    PARSER_REGISTRY = {
        "sbi_savings":  {"func": ..., "bank": "SBI",  "account_type": "SAVINGS"},
        "axis_savings": {"func": ..., "bank": "AXIS", "account_type": "SAVINGS"},
        "sbi_loan":     {"func": ..., "bank": "SBI",  "account_type": "LOAN"},
        "cbi_loan":     {"func": ..., "bank": "CBI",  "account_type": "LOAN"},
    }

### Transaction fields produced by all parsers

    bank, account_type, date, value_date, transaction_type, direction,
    amount, debit, credit, balance, counterparty, counterparty_bank,
    upi_id, reference_number, note, raw_details

### Parser detail

    sbi_savings.py
      - Columns: Date, Details, Ref No, Debit, Credit, Balance
      - Transaction types detected: UPI (CR/DR), NEFT, RTGS, IMPS, ATM_CHARGE, INTEREST, ACH
      - Direction from: UPI direction in details string, or debit/credit column

    axis_savings.py
      - Columns: Date, Transaction Details, Chq, Withdrawal, Deposit, Balance
      - Transaction types: IMPS/P2A, NEFT (slash-delimited inward), UPI (CR/DR), RTGS,
        ATM_CHARGE, INTEREST, CHARGE
      - Direction from: Withdrawal (DEBIT) / Deposit (CREDIT) column values

    sbi_loan.py
      - Columns: Post Date, Details, Ref No, Debit, Credit, Balance
      - Transaction types: PRINCIPAL_REPAYMENT, INTEREST_REPAYMENT, COMPOUND_REPAYMENT
      - Also extracts: sanctioned amount, outstanding balance, interest rate, tenure

    cbi_loan.py
      - Columns: Post Date, Details, Ref No, Debit, Credit, Balance
      - Transaction types: INTEREST_CHARGE, PRINCIPAL_REPAYMENT, DISBURSEMENT,
        PENAL_INTEREST, CHARGE
      - Direction from: trailing "DR"/"CR" indicator in balance column


---


## 16. AI Pipeline

### Architecture

    User question
        ↓
    Step 1: SQL Generation
        - Build messages: [system=sql_gen.txt] + [sql_history (last 10)] + [user question]
        - POST /api/chat → Ollama (gemma3:4b)
        - Extract SELECT statement from response
        - Validate: must start with SELECT, no forbidden keywords (INSERT/UPDATE/DROP/etc.)
        - PRAGMA query_only = ON (SQLite engine-level write guard)
        - Execute against tracker.db → rows
        ↓
    Step 2: Answer Generation
        - Build messages: [system=answer.txt] + [chat_history (last 10)] + [question + JSON rows]
        - POST /api/chat → Ollama
        - Return plain-English answer
        ↓
    Persist to DB
        - conversation_messages: role=user, role=sql, role=assistant

### sql_gen.txt prompt structure

    - Role definition (SQLite query generator)
    - Full schema: savings_transactions (all 22 columns), loan_transactions, accounts
    - 16 query rules: date filtering, LOWER() for case-insensitive LIKE, OR+AND parentheses,
      "last N months" → date('now', '-N months'), no date filter for salary questions
    - DB context injected at runtime: date range, accounts, top spend/credit counterparties
    - 11 worked example Q→SQL pairs
    - {question} placeholder

### Safety layers

    1. Keyword blocklist regex: INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA
    2. Must start with SELECT
    3. SQLite PRAGMA query_only = ON (engine refuses writes even if blocklist missed anything)
    4. Results capped at 50 rows fetched; 15 rows max sent to answer prompt

### Conversation history

    Two separate in-memory lists (both capped at 10 messages):
      _sql_history:  [{"role":"user","content":"<question>"}, {"role":"assistant","content":"<sql>"}]
      _chat_history: [{"role":"user","content":"<question>"}, {"role":"assistant","content":"<answer>"}]

    Persisted to tracker.db in conversation_messages.
    On startup: last conversation_id loaded from DB, histories rebuilt, chat log replayed.
    On Clear: new conversation row created, both histories reset.

### Configuration (ai_config.json)

    {
      "model":       "gemma3:4b",       Ollama model name
      "endpoint":    "http://localhost:11434",
      "temperature": 0.1,               Low = more deterministic SQL
      "timeout":     60                 Seconds before giving up
    }

    File is optional — defaults are used if it doesn't exist.
    File is gitignored so model preferences stay private per-machine.


---


## 17. Configuration Files

### config.json (gitignored)

    [
      {
        "account_name": "SBI Savings",      Display name shown in the app
        "parser":       "sbi_savings",      Must match a key in PARSER_REGISTRY
        "folder":       "statements/sbi_savings",  Relative path to PDF folder
        "password":     "yourpassword"      PDF password, or null if none
      }
    ]

### categories.json (gitignored)

    {
      "Zomato":   "Food & Dining",
      "Netflix":  "Subscriptions",
      "Airtel":   "Telecom"
      ...
    }

    Pattern matching is case-insensitive substring search.
    The app ships with 18 built-in defaults; users add more via CLI or UI.
    Running `python cli.py category apply` re-applies all rules to existing transactions.

### aliases.json (gitignored)

    {
      "IRCTCTOU":  "IRCTC",
      "JAYARAMA":  "Jayaraman Broker"
    }

    Applied at import time via apply_alias(counterparty).
    If alias differs from raw name, alias_name column is set in the DB.
    Raw counterparty is always preserved unchanged.

### ai_config.json (gitignored)

    Copy from ai_config.example.json. Optional — defaults work out of the box.

### .gitignore

    tracker.db, config.json, categories.json, aliases.json, ai_config.json
    statements/**/*.pdf, statements/**/*.PDF
    __pycache__/, *.pyc, .venv/, venv/


---


## 18. How to Add a New Bank Parser

1. Create parsers/yourbank_savings.py

   Implement a function with this signature:

       def load_statement(pdf_path, password=None, account_number=None) -> list[dict]:

   Each dict in the returned list must contain at minimum:
       bank, date, transaction_type, direction, debit, credit, balance, raw_details

   Optional fields: counterparty, counterparty_bank, upi_id, reference_number, note

2. Register the parser in parsers/__init__.py

       from parsers.yourbank_savings import load_statement as yourbank_load

       PARSER_REGISTRY["yourbank_savings"] = {
           "func":         yourbank_load,
           "bank":         "YOURBANK",
           "account_type": "SAVINGS",
       }

3. Add an entry to config.json

       {
         "account_name": "Your Bank Savings",
         "parser":       "yourbank_savings",
         "folder":       "statements/yourbank_savings",
         "password":     null
       }

4. Test with:

       python cli.py import --file statements/yourbank_savings/statement.pdf \
                            --parser yourbank_savings \
                            --account-name "Your Bank Savings"

Refer to parsers/base.py for shared utilities:
  - extract_tables_from_pdf(pdf_path, password) → list of rows
  - find_header_row(rows, keywords) → index of header row
  - col_index(header, candidates) → column index
  - parse_amount(text) → float or None


---


## 19. Dependencies

    pdfplumber      Extracts tables from PDF bank statements
    textual         Terminal UI framework (TUI) — https://textual.textualize.io
    httpx           Async HTTP client for Ollama API calls

Install all with:

    pip install -r requirements.txt

External tools (not Python packages):
    Ollama          Local LLM runtime — https://ollama.com
                    Required only for the Ask AI tab.
                    Model: gemma3:4b (default, ~2.5 GB)
    SQLite          Built into Python's standard library — no installation needed.


---


## Error Codes Reference

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

Built with Python · Textual · pdfplumber · SQLite · Ollama
All data stays on your machine.
