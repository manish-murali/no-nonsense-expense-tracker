# Personal Expense Tracker

A private, local-first personal finance tool that reads your bank statements (PDF),
organises all your transactions, and lets you ask questions about your money in plain
English — without sending any data to the cloud.

Everything runs on your own computer. Your bank data never leaves your machine.

---

## 1. What This App Does

Tracking your money shouldn't mean sacrificing your privacy or being locked behind a paywall. Most apps prioritize flashy, complicated visuals over what actually matters: clear visibility and total data security.

This app solves that by transforming cryptic bank statements into a clean, actionable view of your finances. By accurately parsing your data and keeping it strictly on your own hardware, you get a private, organized look at where your money goes. You stay in total control easily refining categories where needed and using a local AI assistant to ask questions about your money in plain English.



---


## 2. Key Features


### Automatic Bank Statement Import
Drop your PDF bank statements into a folder and the app reads them automatically.
It handles password-protected PDFs, skips files it has already imported (no duplicates),
and supports multiple accounts at the same time.

Currently supported banks: SBI, Axis, CBI.



### Smart Categorisation
Transactions are auto-tagged (e.g., Zomato → Food). If the machine needs help, the interface is built for instant manual corrections.


### Readable Merchant Name
Manually convert messy bank codes like IRCTCTOU into clean names like IRCTC. Once updated, the name changes across your entire history.
No nonsense essential Widgets
A no-nonsense dashboard focused on utility. Simple widgets track:
•	Account & Loan Balances
•	Spending vs. Income
•	Recent Transactions & Category Trends


### Master Ledger
A master list to search, filter, and edit your data. Updating a category or name here reflects everywhere in the app.


### Grannular Tagging
Add specific tags to individual transactions (e.g., "Birthday Gift") without affecting the broader category rules.


### Local AI Chat
Ask financial questions in plain English. Powered by Ollama, the AI runs 100% on your hardware. No data ever leaves your computer.


### Local-First
No accounts, no cloud, and no internet required. All financial records are stored in a single local file (tracker.db, SQL Lite database) that you control.


---


## 3. Screenshots & Interface Overview

The app has four screens:
#### Overview: Balances, monthly chart, recent transactions
<img width="2739" height="1514" alt="Overview (1)" src="https://github.com/user-attachments/assets/eef78d6b-6b85-468d-b3b5-4154ad911a2c" />

#### Expenses & Trends: Category breakdown, top merchants, transaction detail
<img width="2739" height="1514" alt="Expenses   Trends (1)" src="https://github.com/user-attachments/assets/01b0fff7-91c7-4a64-a3ee-b10ca1b8245d" />

#### Ask AI:Chat with your bank statements
<img width="2739" height="1514" alt="Al Chatbot (1)" src="https://github.com/user-attachments/assets/5259bff8-1036-49bb-9868-c25a3e5aa9f8" />

#### Transaction Log Full searchable, editable transaction table
<img width="2739" height="1514" alt="transaction log (1)" src="https://github.com/user-attachments/assets/3380f5a8-a319-4a9c-bc6a-5f2718a81f83" />


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
