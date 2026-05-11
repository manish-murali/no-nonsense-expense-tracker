from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, DataTable, Input, Button
from rich.text import Text

from storage import db
from display_name import add_alias
from categorizer import add_rule


class TransactionLogTab(Vertical):

    # Column indices (0-based, matching add_columns order)
    _COL_ALIAS       = 8
    _COL_CATEGORY    = 9
    _COL_SUBCATEGORY = 10

    def compose(self) -> ComposeResult:
        with Horizontal(id="txn-filter-row"):
            yield Input(placeholder="Search by account, counterparty, type, date...", id="txn-search")
            yield Button("All",     id="filter-all",     variant="primary",  classes="filter-btn")
            yield Button("Credits", id="filter-credit",  variant="success",  classes="filter-btn")
            yield Button("Debits",  id="filter-debit",   variant="error",    classes="filter-btn")
            yield Button("Savings", id="filter-savings", variant="default",  classes="filter-btn")
            yield Button("Loans",   id="filter-loan",    variant="default",  classes="filter-btn")

        yield Static("", id="txn-summary")
        yield DataTable(id="txn-table", zebra_stripes=True, cursor_type="cell")

        # Edit panel — always visible, content adapts to clicked column
        with Horizontal(id="txn-edit-panel"):
            yield Static(
                "[dim]← Click [yellow]Display Name[/], [cyan]Category[/] or [magenta]Tag[/] cell to edit[/]",
                id="txn-edit-info"
            )
            yield Input(placeholder="Click a cell to edit...", id="tag-input")
            yield Button("Save",  id="save-tag",  variant="primary")
            yield Button("Clear", id="clear-tag", variant="default")

    def on_mount(self) -> None:
        self._current_account_type: str | None   = None
        self._current_direction: str | None      = None
        self._selected_txn_id: str | None        = None
        self._selected_counterparty: str | None  = None
        self._edit_mode: str | None              = None   # "alias" | "category" | "tag"
        self._rows: list[dict]                   = []
        self._loading: bool                      = False  # suppress cell events during reload

        # Force panel height and styling via Python styles
        panel = self.query_one("#txn-edit-panel")
        panel.styles.height         = 4
        panel.styles.border_top     = ("solid", "#388bfd")
        panel.styles.background     = "#161b22"
        panel.styles.padding        = (0, 2)

        self._set_edit_active(False)
        self._load(account_type=None, direction=None, search=None)

    def _set_edit_active(self, active: bool) -> None:
        inp  = self.query_one("#tag-input", Input)
        save = self.query_one("#save-tag",  Button)
        clr  = self.query_one("#clear-tag", Button)
        inp.disabled  = not active
        save.disabled = not active
        clr.disabled  = not active

    def _load(self, account_type: str | None, direction: str | None, search: str | None) -> None:
        self._loading = True
        self._rows = db.get_all_transactions(account_type=account_type, direction=direction,
                                             search=search, limit=1000)
        table = self.query_one("#txn-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Account", "Acct Type", "Type", "Dir",
                          "Debit", "Credit", "Counterparty",
                          "Display Name", "Category", "Tag")

        total_debit = total_credit = 0.0
        for r in self._rows:
            direction_val = r["direction"] or "UNKNOWN"
            dir_text      = (Text("↑ IN ", style="green") if direction_val == "CREDIT"
                             else Text("↓ OUT", style="red"))
            debit  = r["debit"]  or 0
            credit = r["credit"] or 0

            alias_text = (Text(r["display_name"], style="yellow")
                          if r.get("display_name") else Text("—", style="dim"))

            cat_text = Text(r.get("category") or "—")

            subcat = r.get("tag")
            subcat_text = (Text(f"★ {subcat}", style="magenta bold")
                           if subcat else Text("—", style="dim"))

            table.add_row(
                r["date"], r["account_name"], r["account_type"],
                r["transaction_type"], dir_text,
                f"₹{debit:,.2f}"  if debit  else "—",
                f"₹{credit:,.2f}" if credit else "—",
                r.get("counterparty") or "—",
                alias_text,
                cat_text,
                subcat_text,
                key=r["txn_id"],
            )
            total_debit  += debit
            total_credit += credit

        table.move_cursor(row=0)
        self._loading = False
        count = len(self._rows)
        self.query_one("#txn-summary", Static).update(
            f"  [dim]{count} transactions[/]   "
            f"[green]Credits: ₹{total_credit:,.2f}[/]   "
            f"[red]Debits: ₹{total_debit:,.2f}[/]   "
            f"[cyan]Net: ₹{total_credit - total_debit:,.2f}[/]\n"
        )

    def refresh_data(self) -> None:
        self._reload_current()

    def _reload_current(self) -> None:
        search = self.query_one("#txn-search", Input).value.strip() or None
        self._load(self._current_account_type, self._current_direction, search)

    # ── Cell highlight → update edit panel ───────────────────────────

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        if event.data_table.id != "txn-table":
            return
        if self._loading:           # ignore cursor moves caused by _load()
            return
        if event.cell_key is None or event.cell_key.row_key is None:
            return

        txn_id = str(event.cell_key.row_key.value)
        row    = next((r for r in self._rows if r["txn_id"] == txn_id), None)
        col    = event.coordinate.column

        if row is None or row.get("account_type") == "LOAN":
            self.query_one("#txn-edit-info", Static).update(
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
            self.query_one("#txn-edit-info", Static).update(
                f"[bold]Alias for:[/] [yellow]{cp}[/]  "
                f"[dim](updates all rows with this counterparty)[/]"
            )
            inp = self.query_one("#tag-input", Input)
            inp.placeholder = "Clean name (e.g. Zomato, Dad, Self Transfer)..."
            inp.value       = row.get("merchant_name") or ""
            self._set_edit_active(True)

        elif col == self._COL_CATEGORY:
            self._edit_mode = "category"
            cp = (row.get("merchant_name") or row.get("counterparty") or "—")[:40]
            self.query_one("#txn-edit-info", Static).update(
                f"[bold]Category for:[/] [cyan]{cp}[/]  "
                f"[dim](updates all rows with this counterparty + saves to categories.json)[/]"
            )
            inp = self.query_one("#tag-input", Input)
            inp.placeholder = "Category (e.g. Food & Dining, Rent, Transport)..."
            inp.value       = row.get("category") or ""
            self._set_edit_active(True)

        elif col == self._COL_SUBCATEGORY:
            self._edit_mode = "tag"
            cp = (row.get("merchant_name") or row.get("counterparty") or "—")[:30]
            self.query_one("#txn-edit-info", Static).update(
                f"[bold]Tag:[/] [magenta]{row['date']}  {cp}[/]  "
                f"[dim](this transaction only)[/]"
            )
            inp = self.query_one("#tag-input", Input)
            inp.placeholder = "Override (e.g. Salary, Car Insurance, Dad's Rent)..."
            inp.value       = row.get("tag") or ""
            self._set_edit_active(True)

        else:
            self._edit_mode = None
            self.query_one("#txn-edit-info", Static).update(
                "[dim]← Click [yellow]Display Name[/], [cyan]Category[/] or [magenta]Tag[/] cell to edit[/]"
            )
            self.query_one("#tag-input", Input).value = ""
            self._set_edit_active(False)

    # ── Button handling ───────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        search = self.query_one("#txn-search", Input).value.strip() or None

        # Filter buttons
        mapping = {
            "filter-all":     (None,      None),
            "filter-credit":  (None,      "CREDIT"),
            "filter-debit":   (None,      "DEBIT"),
            "filter-savings": ("SAVINGS", None),
            "filter-loan":    ("LOAN",    None),
        }
        if event.button.id in mapping:
            acct_type, direction = mapping[event.button.id]
            self._current_account_type = acct_type
            self._current_direction    = direction
            self._load(acct_type, direction, search)
            if event.button.id == "filter-all":
                self.query_one("#txn-search", Input).value = ""
            return

        if event.button.id == "save-tag":
            val = self.query_one("#tag-input", Input).value.strip()

            if self._edit_mode == "alias" and self._selected_counterparty:
                try:
                    add_alias(self._selected_counterparty, val)
                    n = db.set_alias_for_counterparty(self._selected_counterparty, val or None)
                    self.app.notify(f"Alias saved — {n} row(s) updated", severity="information")
                except Exception as e:
                    self.app.notify(f"Error saving alias: {e}", severity="error")
                self._reload_current()

            elif self._edit_mode == "category" and self._selected_counterparty:
                try:
                    add_rule(self._selected_counterparty, val)
                    n = db.set_category_for_counterparty(self._selected_counterparty, val or None)
                    self.app.notify(f"Category saved — {n} row(s) updated", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self._reload_current()

            elif self._edit_mode == "tag" and self._selected_txn_id:
                try:
                    db.set_tag(self._selected_txn_id, val or None)
                    self.app.notify("Tag saved", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self._reload_current()
            return

        if event.button.id == "clear-tag":
            if self._edit_mode == "alias" and self._selected_counterparty:
                try:
                    add_alias(self._selected_counterparty, "")
                    db.set_alias_for_counterparty(self._selected_counterparty, None)
                    self.app.notify("Alias cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#tag-input", Input).value = ""
                self._reload_current()

            elif self._edit_mode == "category" and self._selected_counterparty:
                try:
                    db.set_category_for_counterparty(self._selected_counterparty, None)
                    self.app.notify("Category cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#tag-input", Input).value = ""
                self._reload_current()

            elif self._edit_mode == "tag" and self._selected_txn_id:
                try:
                    db.set_tag(self._selected_txn_id, None)
                    self.app.notify("Tag cleared", severity="information")
                except Exception as e:
                    self.app.notify(f"Error: {e}", severity="error")
                self.query_one("#tag-input", Input).value = ""
                self._reload_current()
            return

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "txn-search":
            q = event.value.strip()
            self._load(None, None, q if q else None)
