# Personal Expense Tracker

A private, local-first personal finance tool that reads your bank statements (PDF),
organises all your transactions, and lets you ask questions about your money in plain
English — without sending any data to the cloud.

Everything runs on your own computer. Your bank data never leaves your machine.

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

Currently supported banks: SBI, Axis, CBI.


### Smart Auto-Categorisation
Every transaction is automatically assigned a category based on who you paid.
Zomato becomes "Food & Dining". Netflix becomes "Subscriptions". Airtel becomes "Telecom".
You can add your own rules and change any category at any time.


### Clean Display Names
Banks display ugly codes like "IRCTCTOU" or "OGS (INDIA) PVT LTD (G3-ITP-".
The display name system lets you replace these with readable names like "IRCTC" or "Optum".
Once set, the clean name shows everywhere and future imports use it automatically.


### Interactive Dashboard (Overview Tab)
See all your account balances on one screen, a bar chart of spending vs income
for the last 3 months, and your 25 most recent transactions — all at a glance.


### Spending Trends (Expenses & Trends Tab)
A visual breakdown of your spending by category with bar charts.
Click any merchant to see every transaction you've had with them.


### Full Transaction Log
Browse all transactions with search and filter. Filter by Credits, Debits,
Savings accounts, or Loans. Search by merchant name, date, or transaction type.
Click any Display Name, Category, or Tag cell to edit it directly.


### Per-Transaction Tags
If the automatic category isn't specific enough, you can add a Tag to any individual
transaction. Example: Category = "Shopping", Tag = "Birthday gift".
Tags only change that one transaction — not all of them.


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


## 3. Screenshots & Interface Overview

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


## Documentation

| Guide | Contents |
|---|---|
| [Getting Started](docs/getting-started.md) | Installation, setup, first import |
| [User Manual](docs/user-manual.md) | Using every tab, categories, display names, AI, shortcuts, CLI |
| [Technical Reference](docs/technical-reference.md) | Schema, parsers, AI pipeline, adding a new bank |

---

Built with Python · Textual · pdfplumber · SQLite · Ollama
All data stays on your machine.
