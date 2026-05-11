# User Manual

Everything you need to use the app day-to-day — tabs, editing, categories,
display names, AI chat, shortcuts, and the command-line interface.

---

## Table of Contents

  1. Using the App — Tab by Tab
  2. Categorising Your Spending
  3. Display Names — Clean Up Merchant Names
  4. Tags — Per-Transaction Notes
  5. Ask AI — Chat With Your Data
  6. Keyboard Shortcuts
  7. Command-Line Reference


---


## 1. Using the App — Tab by Tab


### Overview Tab (press 1)

Shows three sections:

**Account Balances**
One card per savings account showing the current balance and the date of the
last statement imported. A "Total Savings" card shows the combined balance.
Loan accounts appear below in red, showing what you still owe.

**Monthly Spend Chart**
A simple bar chart comparing expenses (red bars) and income (green bars)
for the last 3 months. The longest bar represents the highest value.

**Recent Transactions**
The 25 most recent transactions across all accounts.
Columns: Date, Account, Direction (↑ IN / ↓ OUT), Type, Amount, Counterparty,
         Display Name, Category, Tag.
Click any Display Name, Category, or Tag cell to edit it directly.


### Expenses & Trends Tab (press 2)

**Spending by Category**
A bar chart of your total spending broken down by category.
Longer bar = more money spent in that category.

**Top 10 Merchants**
A table of the merchants where you spend the most, showing:
total spent, number of transactions, and average per transaction.

**Merchant Detail**
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

The AI shows the query it ran (in small text below the chat) so you can verify
what data it fetched. Press Clear to start a new conversation.

Note: Ollama must be running for this tab to work. See the [setup guide](getting-started.md).


### Transaction Log Tab (press 4)

A complete, searchable view of every transaction.

**Search**
Type in the search box to filter by merchant name, account, date, or type.
Results update live as you type.

**Filter Buttons**
All | Credits | Debits | Savings | Loans
Click to filter the entire table by transaction direction or account type.

**Editing**
Click any cell in the Display Name, Category, or Tag column to open the edit panel.

  - Display Name edit: Updates ALL transactions with the same counterparty, saves to display_name.json
  - Category edit:     Updates ALL transactions with the same counterparty, saves to categories.json
  - Tag edit:          Updates ONLY that single transaction

Press Save to apply, Clear to remove the value.


---


## 2. Categorising Your Spending

Categories are assigned automatically when you import a statement.
The app matches the merchant name against rules stored in `categories.json`.


### View existing categories

    python cli.py category list


### Add a new rule

    python cli.py category add --pattern "BookMyShow" --category "Entertainment"

This saves the rule and immediately applies it to all matching existing transactions.


### Re-apply all rules

    python cli.py category apply

Useful after adding many rules at once, or after importing a new statement.


### Edit a category from the UI

In the Transaction Log or the Overview Recent Transactions table:
  1. Click a cell in the Category column
  2. Type the category name in the edit panel at the bottom
  3. Press Save

This updates all transactions from the same merchant and saves the rule to `categories.json`.


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


## 3. Display Names — Clean Up Merchant Names

Banks use raw transaction codes that are hard to read.
Display names let you replace these with something human-readable.

Example: "OGS (INDIA) PVT LTD (G3-ITP-" → "Optum"

The raw name from the bank is always preserved in the database.
The display name shows in the Display Name column everywhere in the app.


### Add a display name from the UI

In the Transaction Log or Overview table:
  1. Click a cell in the Display Name column
  2. Type the clean name in the edit panel
  3. Press Save

All transactions from the same counterparty are updated immediately.
Press Clear to remove the display name.


### Add a display name via command line

    python cli.py alias add --counterparty "IRCTCTOU" --alias "IRCTC"


### List existing display names

    python cli.py alias list


---


## 4. Tags — Per-Transaction Notes

Tags are a way to add a personal label to one specific transaction without
changing its category or affecting any other transaction.

Use case: your Category is "Shopping" but you want to note this particular
purchase was a "Birthday gift". Set the Tag to "Birthday gift" — it only
applies to that one row.


### Set a tag from the UI

In the Transaction Log or Overview table:
  1. Click a cell in the Tag column
  2. Type the tag in the edit panel
  3. Press Save

Press Clear to remove the tag.


---


## 5. Ask AI — Chat With Your Data

The AI assistant understands your transaction database and answers questions in plain
English. It is powered by Ollama, a tool that runs AI models locally on your computer.


### How it works

When you ask a question, the AI does two things:

  1. Figures out what data to fetch from your transactions
     (based on your question, account history, and merchant names)

  2. Turns that data into a human-readable answer
     (in ₹ amounts, DD/MM/YYYY dates, plain sentences)

The small line below the chat labelled "SQL →" shows exactly what it fetched —
you can verify the AI is looking at the right data.


### Tips for better results

  - Be specific: "How much did I spend on Zomato last month?" works better than "Zomato?"
  - Use follow-up questions: "What about February?" after asking about March
    — the AI remembers the context.
  - If you get a wrong answer, press Clear and rephrase the question.
  - The AI knows your account names, top merchants, and date range automatically.


### Conversation memory

Conversations are saved between sessions. When you reopen the app, the last
conversation is restored. Press Clear to start fresh (old conversations are kept
in the database, not deleted).


### AI model options

The default model is `gemma3:4b`. You can switch by creating `ai_config.json`
(copy from `ai_config.example.json`) and changing the `model` field.

Alternatives:
  - `gemma3:12b`   — Better answers, needs more RAM (~8 GB)
  - `llama3.2:3b`  — Faster, slightly less accurate
  - `phi4-mini`    — Good at reasoning, compact size


---


## 6. Keyboard Shortcuts

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


## 7. Command-Line Reference

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

    # Display name management
    python cli.py alias list
    python cli.py alias add --counterparty "RAW NAME" --alias "CLEAN NAME"


---

← [Getting Started](getting-started.md) · [Technical Reference →](technical-reference.md)
