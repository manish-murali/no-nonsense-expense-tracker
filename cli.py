"""
Expense Tracker CLI

Commands:
  import      Import a PDF statement into the database
  accounts    List all registered accounts
  summary     Print a financial summary
  category    Manage category rules (add / list / apply)

Examples:
  python cli.py import --file statement.pdf --parser sbi_savings \
                       --account-name "SBI Savings" --password PASS
  python cli.py accounts
  python cli.py summary
  python cli.py category add --pattern "Zomato" --category "Food"
  python cli.py category list
  python cli.py category apply
"""

import argparse
import sys
from pathlib import Path

from storage     import db
from importer    import import_statement
from categorizer import seed_defaults, recategorize_all, add_rule, get_rules
from aliases     import add_alias, get_aliases
from parsers     import PARSER_REGISTRY


# ── Helpers ───────────────────────────────────────────────────────────

def _fmt(n: float | None) -> str:
    return f"₹{n:>12,.2f}" if n is not None else "          —"


# ── Command handlers ──────────────────────────────────────────────────

def cmd_import(args):
    print(f"\n  Importing: {args.file}")
    print(f"  Parser   : {args.parser}")
    print(f"  Account  : {args.account_name}\n")

    result = import_statement(
        pdf_path       = args.file,
        parser_name    = args.parser,
        account_name   = args.account_name,
        password       = args.password,
        account_number = args.account_number,
        force          = args.force,
    )

    if result["skipped"]:
        print("  ⚠  Already imported (use --force to re-import).\n")
        return

    print(f"  ✓ Found      : {result['found']:>4} transactions")
    print(f"  ✓ Inserted   : {result['inserted']:>4} new")
    print(f"  ✓ Duplicates : {result['duplicates']:>4} skipped")
    print()


def cmd_import_all(args):
    import json
    from pathlib import Path

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"  ✗ Config file not found: {config_path}")
        return

    with open(config_path) as f:
        accounts = json.load(f)

    total_found = total_inserted = total_dupes = total_skipped = 0

    for entry in accounts:
        folder = Path(entry["folder"])
        if not folder.exists():
            print(f"  [WARN] Folder not found, skipping: {folder}")
            continue

        pdfs = sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))
        if not pdfs:
            print(f"  [SKIP] No PDFs in: {folder}")
            continue

        print(f"\n  ── {entry['account_name']} ({entry['parser']}) ──")
        for pdf in pdfs:
            try:
                result = import_statement(
                    pdf_path       = pdf,
                    parser_name    = entry["parser"],
                    account_name   = entry["account_name"],
                    password       = entry.get("password"),
                    force          = getattr(args, "force", False),
                )
            except Exception as e:
                print(f"    {pdf.name:<40} ✗ ERROR: {e}")
                continue

            if result["skipped"]:
                print(f"    {pdf.name:<40} already imported")
                total_skipped += 1
            else:
                print(f"    {pdf.name:<40} "
                      f"+{result['inserted']} new  "
                      f"{result['duplicates']} dupes")
                total_found    += result["found"]
                total_inserted += result["inserted"]
                total_dupes    += result["duplicates"]

    print(f"\n  ── Summary ──────────────────────────────")
    print(f"  Inserted   : {total_inserted}")
    print(f"  Duplicates : {total_dupes}")
    print(f"  Skipped    : {total_skipped} (already imported)")
    print()


def cmd_accounts(args):
    db.init_db()
    accounts = db.get_accounts()
    if not accounts:
        print("\n  No accounts registered yet. Run `import` first.\n")
        return

    print(f"\n  {'Account Name':<25} {'Bank':<6} {'Type':<8} {'Number'}")
    print(f"  {'-'*25} {'-'*6} {'-'*8} {'-'*12}")
    for a in accounts:
        print(f"  {a['account_name']:<25} {a['bank']:<6} {a['account_type']:<8} {a['account_number'] or '—'}")
    print()


def cmd_summary(args):
    db.init_db()
    savings = db.get_savings_balances()
    loans   = db.get_loan_balances()

    total_savings = sum(r["balance"] or 0 for r in savings)
    total_loan    = sum(r["balance"] or 0 for r in loans)

    print("\n" + "=" * 55)
    print("  EXPENSE TRACKER — SUMMARY")
    print("=" * 55)

    print("\n  Savings Accounts")
    print(f"  {'Account':<25} {'Balance':>14}")
    print(f"  {'-'*25} {'-'*14}")
    for r in savings:
        print(f"  {r['account_name']:<25} {_fmt(r['balance'])}")
    print(f"  {'TOTAL SAVINGS':<25} {_fmt(total_savings)}")

    print("\n  Loan Accounts")
    print(f"  {'Account':<25} {'Outstanding':>14}")
    print(f"  {'-'*25} {'-'*14}")
    for r in loans:
        print(f"  {r['account_name']:<25} {_fmt(r['balance'])}")
    print(f"  {'TOTAL OUTSTANDING':<25} {_fmt(total_loan)}")

    print("\n  Monthly Spend (last 6 months)")
    print(f"  {'Month':<10} {'Expenses':>14} {'Income':>14}")
    print(f"  {'-'*10} {'-'*14} {'-'*14}")
    for m in db.get_monthly_spend(6):
        print(f"  {m['month']:<10} {_fmt(m['total_debit'])} {_fmt(m['total_credit'])}")

    print("\n  Top 5 Merchants")
    print(f"  {'Merchant':<22} {'Spent':>12} {'Txns':>5}")
    print(f"  {'-'*22} {'-'*12} {'-'*5}")
    for m in db.get_top_merchants(5):
        print(f"  {(m['counterparty'] or '—'):<22} {_fmt(m['total_spent'])} {m['txn_count']:>5}")

    print("=" * 55 + "\n")


def cmd_category_add(args):
    add_rule(args.pattern, args.category)
    print(f"  Rule added: '{args.pattern}' → '{args.category}'")


def cmd_category_list(args):
    rules = get_rules()
    if not rules:
        print("  No rules defined yet.")
        return
    print(f"\n  {'Pattern':<25} {'Category'}")
    print(f"  {'-'*25} {'-'*25}")
    for pattern, category in sorted(rules.items()):
        print(f"  {pattern:<25} {category}")
    print()


def cmd_category_apply(args):
    db.init_db()
    updated = recategorize_all()
    print(f"  Re-categorized {updated} transactions.")


def cmd_alias_add(args):
    add_alias(args.raw, args.clean)
    print(f"  Alias added: '{args.raw}' → '{args.clean}'")


def cmd_alias_list(args):
    aliases = get_aliases()
    if not aliases:
        print("  No aliases defined yet.")
        return
    print(f"\n  {'Raw Name':<35} {'Clean Name'}")
    print(f"  {'-'*35} {'-'*25}")
    for raw, clean in sorted(aliases.items()):
        print(f"  {raw:<35} {clean}")
    print()


# ── Argument parser ───────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="Expense Tracker CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")

    # import
    pi = sub.add_parser("import", help="Import a PDF bank statement")
    pi.add_argument("--file",           required=True,  help="Path to PDF")
    pi.add_argument("--parser",         required=True,  choices=list(PARSER_REGISTRY),
                    help="Parser to use")
    pi.add_argument("--account-name",   required=True,  dest="account_name",
                    help="Friendly account name, e.g. 'SBI Savings'")
    pi.add_argument("--password",       default=None,   help="PDF password (if any)")
    pi.add_argument("--account-number", default=None,   dest="account_number",
                    help="Account number (e.g. XXXX1234)")
    pi.add_argument("--force",          action="store_true",
                    help="Re-import even if already imported")

    # import-all
    pia = sub.add_parser("import-all", help="Import all PDFs from all account folders (uses config.json)")
    pia.add_argument("--config", default="config.json", help="Path to config.json (default: config.json)")
    pia.add_argument("--force",  action="store_true",   help="Re-import already-imported files")

    # accounts
    sub.add_parser("accounts", help="List registered accounts")

    # summary
    sub.add_parser("summary", help="Print financial summary")

    # category
    pc  = sub.add_parser("category", help="Manage category rules")
    pcs = pc.add_subparsers(dest="cat_command")

    pca = pcs.add_parser("add",   help="Add a category rule")
    pca.add_argument("--pattern",  required=True)
    pca.add_argument("--category", required=True)

    pcs.add_parser("list",  help="List all category rules")
    pcs.add_parser("apply", help="Re-apply rules to all transactions")

    # alias
    pa  = sub.add_parser("alias", help="Manage counterparty aliases")
    pas = pa.add_subparsers(dest="alias_command")

    paa = pas.add_parser("add",  help="Add a counterparty alias")
    paa.add_argument("--raw",   required=True, help="Raw name from bank statement")
    paa.add_argument("--clean", required=True, help="Clean display name")

    pas.add_parser("list", help="List all aliases")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.command == "import":
        cmd_import(args)
    elif args.command == "import-all":
        cmd_import_all(args)
    elif args.command == "accounts":
        cmd_accounts(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "category":
        if args.cat_command == "add":
            cmd_category_add(args)
        elif args.cat_command == "list":
            cmd_category_list(args)
        elif args.cat_command == "apply":
            cmd_category_apply(args)
        else:
            parser.parse_args(["category", "--help"])
    elif args.command == "alias":
        if args.alias_command == "add":
            cmd_alias_add(args)
        elif args.alias_command == "list":
            cmd_alias_list(args)
        else:
            parser.parse_args(["alias", "--help"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
