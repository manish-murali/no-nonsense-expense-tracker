# Getting Started — Setup Guide

This guide takes you from zero to a working app with your bank data imported.

---

## Step 1 — Check Python is installed

Open a terminal and run:

    python --version

You need Python 3.11 or newer. If you don't have it, download it from python.org.


---


## Step 2 — Download the project

If you received this as a folder, skip this step.
If you're cloning from GitHub:

    git clone https://github.com/manish-murali/no-nonsense-expense-tracker.git
    cd no-nonsense-expense-tracker


---


## Step 3 — Install dependencies

    pip install -r requirements.txt

This installs three libraries: pdfplumber (reads PDFs), textual (the visual interface),
and httpx (for AI communication).


---


## Step 4 — Create your account configuration

Create a file called `config.json` in the project folder. This tells the app which bank
accounts you have and where to find their statements.

Example `config.json`:

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

  - `sbi_savings`  — SBI savings / current account statements
  - `axis_savings` — Axis Bank savings account statements
  - `sbi_loan`     — SBI Gold Loan statements
  - `cbi_loan`     — CBI Education Loan statements

If your PDF has no password, use: `"password": null`


---


## Step 5 — Create statement folders

Create a `statements/` folder in the project directory, then one subfolder per account
matching the `folder` paths in `config.json`:

    statements/
      sbi_savings/
      axis_savings/

Drop your PDF bank statements into the matching subfolder.


---


## Step 6 — Launch the app

    python app.py

The app will automatically import any new PDFs it finds on startup and show a
notification with how many new transactions were added.


---


## Step 7 — Set up AI (optional)

To use the Ask AI tab, you need Ollama installed on your machine.

    # Install Ollama (macOS)
    brew install ollama

    # Start Ollama (keep this terminal open, or use brew services below)
    ollama serve

    # Pull the AI model — one-time download, ~2.5 GB
    ollama pull gemma3:4b

    # Optional: start Ollama automatically on login
    brew services start ollama

Once Ollama is running, launch the app. The Ask AI tab will connect automatically.


---


## How to Import Bank Statements


### Automatic import (recommended)

Drop PDF files into the correct `statements/` subfolder and launch the app.
It imports everything automatically on startup — no extra steps needed.


### Manual import via command line

Import a single file:

    python cli.py import \
      --file statements/sbi_savings/mystatement.pdf \
      --parser sbi_savings \
      --account-name "SBI Savings" \
      --password yourpassword

Import all configured accounts at once:

    python cli.py import-all

Force re-import (clears existing data for that account and re-imports):

    python cli.py import-all --force


### Duplicate detection

The app tracks every PDF by a unique fingerprint (SHA-256 hash). If you import the same
file twice it is skipped automatically — no duplicate transactions will appear.


---

← [Back to README](../README.md) · [User Manual →](user-manual.md)
