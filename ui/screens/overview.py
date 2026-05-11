from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Container
from textual.widgets import Static, DataTable, Input, Button
from rich.text import Text

from storage import db
from aliases import add_alias
from categorizer import add_rule
from ui.widgets import Card


def _fmt_date(date_str: str) -> str:
    """Convert YYYY-MM-DD (imported_at) to DD/MM/YYYY. DB dates already stored as DD/MM/YYYY."""
    if not date_str:
        return ""
    try:
        if date_str[4] == "-":   # YYYY-MM-DD from imported_at
            y, m, d = date_str[:10].split("-")
            return f"{d}/{m}/{y}"
    except Exception:
        pass
    return date_str  # already DD/MM/YYYY


class OverviewTab(ScrollableContainer):

    # Column indices for recent-table (0-based)
    _COL_ALIAS       = 6
    _COL_CATEGORY    = 7
    _COL_SUBCATEGORY = 8

    def compose(self) -> ComposeResult:
        yield Container(id="balance-row")
        yield Container(id="loan-row")
        yield Static("\n [bold cyan]● Monthly Spend[/]\n", id="monthly-label")
        yield Static("", id="monthly-chart")
        yield Static("\n [bold cyan]● Recent Transactions[/]\n")
        yield DataTable(id="recent-table", zebra_stripes=True, cursor_type="cell")

        # Edit panel — same pattern as Transaction Log
        with Horizontal(id="overview-edit-panel"):
            yield Static(
                "[dim]← Click [yellow]Display Name[/], [cyan]Category[/] or [magenta]Subcategory[/] cell to edit[/]",
                id="overview-edit-info"
            )
            yield Input(placeholder="Click a cell to edit...", id="overview-edit-input")
            yield Button("Save",  id="overview-save",  variant="primary")
            yield Button("Clear", id="overview-clear", variant="default")

    def on_mount(self) -> None:
        self._recent_rows: list[dict]            = []
        self._selected_txn_id: str | None        = None
        self._selected_counterparty: str | None  = None
        self._edit_mode: str | None              = None   # "alias" | "category" | "subcategory"
        self._loading: bool                      = False

        panel = self.query_one("#overview-edit-panel")
        panel.styles.height     = 4
        panel.styles.border_top = ("solid", "#388bfd")
        panel.styles.background = "#161b22"
        panel.styles.padding    = (0, 2)

        self._set_edit_active(False)
        self.refresh_data()

    def _set_edit_active(self, active: bool) -> None:
        inp  = self.query_one("#overview-edit-input", Input)
        save = self.query_one("#overview-save", Button)
        clr  = self.query_one("#overview-clear", Button)
        inp.disabled  = not active
        save.disabled = not active
        clr.disabled  = not active

    def refresh_data(self) -> None:
        self._load_balances()
        self._load_monthly()
        self._load_recent()

    def _load_balances(self) -> None:
        savings = db.get_savings_balances()
        loans   = db.get_loan_balances()

        total_savings = sum(r["balance"] or 0 for r in savings)
        total_loan    = sum(r["balance"] or 0 for r in loans)

        balance_row = self.query_one("#balance-row", Container)
        balance_row.remove_children()
        for r in savings:
            imported = (r.get("imported_at") or "")[:10]
            sub = []
            if r.get("date"):
                sub.append(f"Last txn: {_fmt_date(r['date'])}")
            if imported:
                sub.append(f"Statement: {_fmt_date(imported)}")
            balance_row.mount(Card(
                r["account_name"],
                f"₹{r['balance']:,.2f}" if r["balance"] is not None else "—",
                color="green", classes="balance-card",
                sub_text="  |  ".join(sub) or None,
            ))
        if savings:
            balance_row.mount(Card(
                "Total Savings", f"₹{total_savings:,.2f}", color="green", classes="balance-card",
            ))

        loan_row = self.query_one("#loan-row", Container)
        loan_row.remove_children()
        for r in loans:
            imported = (r.get("imported_at") or "")[:10]
            sub = []
            if r.get("date"):
                sub.append(f"Last txn: {_fmt_date(r['date'])}")
            if imported:
                sub.append(f"Statement: {_fmt_date(imported)}")
            loan_row.mount(Card(
                r["account_name"],
                f"₹{r['balance']:,.2f}" if r["balance"] is not None else "—",
                color="red", classes="loan-card",
                sub_text="  |  ".join(sub) or None,
            ))
        if loans:
            loan_row.mount(Card(
                "Total Loan Outstanding", f"₹{total_loan:,.2f}", color="red", classes="loan-card",
            ))

        if not savings and not loans:
            balance_row.mount(Static(
                "\n  [dim]No data yet. Run:[/] [cyan]python cli.py import ...[/]\n"
            ))

    def _load_monthly(self) -> None:
        rows = db.get_monthly_spend(3)
        chart = self.query_one("#monthly-chart", Static)
        if not rows:
            chart.update("  [dim]No spend data yet.[/]")
            return

        _MONTH_NAMES = {
            "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
            "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
            "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
        }

        max_val   = max(max(r["total_debit"] or 0, r["total_credit"] or 0) for r in rows) or 1
        bar_width = 28
        lines     = []
        for r in rows:
            d = r["total_debit"]  or 0
            c = r["total_credit"] or 0
            d_bar = "█" * int((d / max_val) * bar_width)
            c_bar = "█" * int((c / max_val) * bar_width)
            year, mon = r["month"].split("-")
            label = f"{_MONTH_NAMES.get(mon, mon)} {year}"
            lines.append(f"  {label:<10}  [red]{d_bar:<{bar_width}}[/] ₹{d:>10,.0f}  [dim]Expenses[/]")
            lines.append(f"  {'':<10}  [green]{c_bar:<{bar_width}}[/] ₹{c:>10,.0f}  [dim]Income[/]")
            lines.append("")
        chart.update("\n".join(lines))

    def _load_recent(self) -> None:
        self._loading = True
        table = self.query_one("#recent-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Account", "Dir", "Type", "Amount",
                          "Counterparty", "Display Name", "Category", "Subcategory")

        self._recent_rows = db.get_recent_transactions(25)
        for r in self._recent_rows:
            direction = r["direction"] or "UNKNOWN"
            dir_text  = Text("↑ IN ", style="green") if direction == "CREDIT" else Text("↓ OUT", style="red")
            amount    = r["credit"] if direction == "CREDIT" else r["debit"]
            amt_str   = f"₹{amount:,.2f}" if amount else "—"

            alias_text = (Text(r["display_name"], style="yellow")
                          if r.get("display_name") else Text("—", style="dim"))

            cat_text = Text(r.get("category") or "—")

            subcat = r.get("subcategory")
            subcat_text = (Text(f"★ {subcat}", style="magenta bold")
                           if subcat else Text("—", style="dim"))

            table.add_row(
                r["date"], r["account_name"], dir_text,
                r["transaction_type"], amt_str,
                r.get("counterparty") or "—",
                alias_text,
                cat_text,
                subcat_text,
                key=r["txn_id"],
            )

        table.move_cursor(row=0)
        self._loading = False

    # ── Cell highlight → update edit panel ───────────────────────────

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        if event.data_table.id != "recent-table":
            return
        if self._loading:
            return
        if event.cell_key is None or event.cell_key.row_key is None:
            return

        txn_id = str(event.cell_key.row_key.value)
        row    = next((r for r in self._recent_rows if r["txn_id"] == txn_id), None)
        col    = event.coordinate.column

        if row is None or row.get("account_type") == "LOAN":
            self.query_one("#overview-edit-info", Static).update(
                "[dim]Loan transactions don't support editing[/]"
            )
            self._set_edit_active(False)
            self._edit_mode             = None
            self._selected_txn_id       = None
            self._selected_counterparty = None
            return

        self._selected_txn_id       = txn_id
        self._selected_counterparty = row.get("counterparty")

        if col == self._COL_ALIAS:
            self._edit_mode = "alias"
            cp = (row.get("counterparty") or "—")[:40]
            self.query_one("#overview-edit-info", Static).update(
                f"[bold]Alias for:[/] [yellow]{cp}[/]  "
                f"[dim](updates all rows with this counterparty)[/]"
            )
            inp = self.query_one("#overview-edit-input", Input)
            inp.placeholder = "Clean name (e.g. Zomato, Dad, Self Transfer)..."
            inp.value       = row.get("merchant_name") or ""
            self._set_edit_active(True)

        elif col == self._COL_CATEGORY:
            self._edit_mode = "category"
            cp = (row.get("merchant_name") or row.get("counterparty") or "—")[:40]
            self.query_one("#overview-edit-info", Static).update(
                f"[bold]Category for:[/] [cyan]{cp}[/]  "
                f"[dim](updates all rows with this counterparty + saves to categories.json)[/]"
            )
            inp = self.query_one("#overview-edit-input", Input)
            inp.placeholder = "Category (e.g. Food & Dining, Rent, Transport)..."
            inp.value       = row.get("category") or ""
            self._set_edit_active(True)

        elif col == self._COL_SUBCATEGORY:
            self._edit_mode = "subcategory"
            cp = (row.get("merchant_name") or row.get("counterparty") or "—")[:30]
            self.query_one("#overview-edit-info", Static).update(
                f"[bold]Subcategory:[/] [magenta]{row['date']}  {cp}[/]  "
                f"[dim](this transaction only)[/]"
            )
            inp = self.query_one("#overview-edit-input", Input)
            inp.placeholder = "Override (e.g. Salary, Car Insurance, Dad's Rent)..."
            inp.value       = row.get("subcategory") or ""
            self._set_edit_active(True)

        else:
            self._edit_mode = None
            self.query_one("#overview-edit-info", Static).update(
                "[dim]← Click [yellow]Display Name[/], [cyan]Category[/] or [magenta]Subcategory[/] cell to edit[/]"
            )
            self.query_one("#overview-edit-input", Input).value = ""
            self._set_edit_active(False)

    # ── Button handling ───────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "overview-save":
            val = self.query_one("#overview-edit-input", Input).value.strip()

            if self._edit_mode == "alias" and self._selected_counterparty:
                try:
                    add_alias(self._selected_counterparty, val)
                    n = db.set_alias_for_counterparty(self._selected_counterparty, val or None)
                    self.app.notify(f"Alias saved — {n} row(s) updated", severity="information")
                except Exception as e:
                    self.app.notify(f"Error saving alias: {e}", severity="error")
                self._load_recent()

            elif self._edit_mode == "category" and self._selected_counterparty:
                try:
                    add_rule(self._selected_counterparty, val)
                    n = db.set_category_for_counterparty(self._selected_counterparty, val or None)
                    self.app.notify(f"Category saved — {n} row(s) updated", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self._load_recent()

            elif self._edit_mode == "subcategory" and self._selected_txn_id:
                try:
                    db.set_subcategory(self._selected_txn_id, val or None)
                    self.app.notify("Subcategory saved", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self._load_recent()

        elif event.button.id == "overview-clear":
            if self._edit_mode == "alias" and self._selected_counterparty:
                try:
                    add_alias(self._selected_counterparty, "")
                    db.set_alias_for_counterparty(self._selected_counterparty, None)
                    self.app.notify("Alias cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#overview-edit-input", Input).value = ""
                self._load_recent()

            elif self._edit_mode == "category" and self._selected_counterparty:
                try:
                    db.set_category_for_counterparty(self._selected_counterparty, None)
                    self.app.notify("Category cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#overview-edit-input", Input).value = ""
                self._load_recent()

            elif self._edit_mode == "subcategory" and self._selected_txn_id:
                try:
                    db.set_subcategory(self._selected_txn_id, None)
                    self.app.notify("Subcategory cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#overview-edit-input", Input).value = ""
                self._load_recent()
