import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane
from textual.worker import Worker

from storage import db
from importer import import_statement
from errors import Err
from ui.screens.overview        import OverviewTab
from ui.screens.expenses        import ExpensesTab
from ui.screens.ask             import AskTab
from ui.screens.transaction_log import TransactionLogTab
from ui.widgets                 import Card

CSS = """
/* ════════ Light mode (base) ════════ */
Screen        { background: #f6f8fa; }
Header        { background: #eaeef2; color: #0550ae; }
Footer        { background: #eaeef2; color: #57606a; }
DataTable     { background: #ffffff; }
DataTable > .datatable--header  { background: #eaeef2; color: #0550ae; }
DataTable > .datatable--cursor  { background: #0969da; }
Button.-primary { background: #0969da; border: tall #218bff; }
Input         { background: #ffffff; color: #24292f; border: tall #d0d7de; }
#import-form  { border: round #d0d7de; }
#chat-log     { border: round #d0d7de; background: #f6f8fa; }
#chat-input-row Input  { border: tall #d0d7de; }
#txn-filter-row Input  { border: tall #d0d7de; }
#txn-summary  { color: #57606a; }

/* ════════ Dark mode overrides ════════ */
App.dark-theme Screen       { background: #0d1117; }
App.dark-theme Header       { background: #161b22; color: #58a6ff; }
App.dark-theme Footer       { background: #161b22; color: #8b949e; }
App.dark-theme DataTable    { background: #161b22; }
App.dark-theme DataTable > .datatable--header { background: #21262d; color: #58a6ff; }
App.dark-theme DataTable > .datatable--cursor { background: #1f6feb; }
App.dark-theme Button.-primary { background: #1f6feb; border: tall #388bfd; }
App.dark-theme Input        { background: #161b22; color: #e6edf3; border: tall #30363d; }
App.dark-theme #chat-log    { border: round #30363d; background: #0d1117; }
App.dark-theme #chat-input-row Input { border: tall #30363d; }
App.dark-theme #txn-filter-row Input { border: tall #30363d; }
App.dark-theme #txn-summary { color: #8b949e; }
App.dark-theme #merchant-detail { border: round #30363d; }
App.dark-theme #overview-edit-panel { background: #161b22; }

/* ════════ Layout (theme-independent) ════════ */
#balance-row, #loan-row {
    height: auto;
    margin: 1 2;
}
.balance-card, .loan-card, .info-card {
    width: 1fr; margin: 0 1; height: auto; min-height: 5;
}
#recent-table, #merchant-table, #md-table {
    margin: 0 2 1 2; height: auto; max-height: 28;
}
#monthly-label { margin: 0 2; }
#monthly-chart { margin: 0 3 1 3; }
#cat-chart     { margin: 0 3 1 3; }
#merchant-detail {
    margin: 1 2 1 2; height: auto;
    border: round #30363d; padding: 0 0 1 0;
}
#merchant-detail #md-table { margin: 0 1; max-height: 15; }
#model-info   { height: auto; margin: 0 2 1 2; }
#chat-log        { margin: 0 2; height: 1fr; min-height: 20; padding: 0 1; }
#sql-disclosure  { margin: 0 2; height: auto; padding: 0 1; }
#chat-input-row  { height: auto; margin: 1 2 0 2; }
#chat-input-row Input  { width: 1fr; }
#chat-input-row Button { margin-left: 1; min-width: 8; }
#txn-filter-row { height: auto; margin: 1 2 0 2; }
#txn-filter-row Input  { width: 1fr; margin-right: 1; }
.filter-btn   { min-width: 10; margin-right: 1; }
#txn-summary  { margin: 0 2; padding: 0 1; }
#txn-table         { margin: 0 2 0 2; height: 1fr; }
#txn-edit-panel    { height: 4; padding: 0 2; align: left middle; }
#txn-edit-info     { width: 1fr; padding: 0 1; }
#subcategory-input { width: 35; margin: 0 1; }
#txn-edit-panel Button { min-width: 8; margin: 0 1; }
#overview-edit-panel    { height: 4; padding: 0 2; align: left middle; margin: 0 2; }
#overview-edit-info     { width: 1fr; padding: 0 1; }
#overview-edit-input    { width: 35; margin: 0 1; }
#overview-edit-panel Button { min-width: 8; margin: 0 1; }
TabbedContent { height: 1fr; }
TabPane       { padding: 0; }
"""


class ExpenseTrackerApp(App):
    CSS   = CSS
    TITLE = "Expense Tracker"
    BINDINGS = [
        ("q",      "quit",                    "Quit"),
        ("1",      "switch_tab('overview')",  "Overview"),
        ("2",      "switch_tab('expenses')",  "Expenses & Trends"),
        ("3",      "switch_tab('ask')",       "Ask AI"),
        ("4",      "switch_tab('txnlog')",    "Transaction Log"),
        ("t",      "toggle_theme",            "Toggle Theme"),
        ("ctrl+r", "refresh_data",            "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs", initial="overview"):
            with TabPane("Overview",         id="overview"): yield OverviewTab()
            with TabPane("Expenses & Trends", id="expenses"): yield ExpensesTab()
            with TabPane("Ask AI 🤖",        id="ask"):      yield AskTab()
            with TabPane("Transaction Log",  id="txnlog"):   yield TransactionLogTab()
        yield Footer()

    def on_mount(self) -> None:
        self.add_class("dark-theme")
        db.init_db()
        self.run_worker(self._auto_import, thread=True)

    async def _auto_import(self) -> None:
        config_path = Path("config.json")
        if not config_path.exists():
            return

        with open(config_path) as f:
            accounts = json.load(f)

        total_inserted = 0
        total_files    = 0
        errors         = []

        for entry in accounts:
            folder = Path(entry["folder"])
            if not folder.exists():
                continue
            password = entry.get("password")
            if isinstance(password, str) and password.startswith("YOUR_"):
                errors.append(str(Err.CONFIG_PLACEHOLDER_PASSWORD.format(account=entry["account_name"])))
                continue

            pdfs = sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))
            for pdf in pdfs:
                try:
                    result = import_statement(
                        pdf_path     = pdf,
                        parser_name  = entry["parser"],
                        account_name = entry["account_name"],
                        password     = password,
                    )
                    if not result["skipped"] and result["inserted"] > 0:
                        total_inserted += result["inserted"]
                        total_files    += 1
                except Exception as e:
                    errors.append(f"{pdf.name}: {e}")

        for err in errors:
            self.call_from_thread(self.notify, err, title="Import Error", severity="error")

        if total_inserted > 0:
            self.call_from_thread(
                self.notify,
                f"Imported {total_inserted} new transactions from {total_files} file(s)",
                title="Auto Import",
            )
            self.call_from_thread(self._refresh_all)

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def action_toggle_theme(self) -> None:
        if self.has_class("dark-theme"):
            self.remove_class("dark-theme")
            mode = "Light"
        else:
            self.add_class("dark-theme")
            mode = "Dark"
        for card in self.query(Card):
            card.refresh()
        self.notify(f"Switched to {mode} mode", title="Theme")

    def action_refresh_data(self) -> None:
        self._refresh_all()
        self.notify("Data refreshed.", title="Refresh")

    def _refresh_all(self) -> None:
        for klass in (OverviewTab, ExpensesTab, TransactionLogTab):
            try:
                self.query_one(klass).refresh_data()
            except Exception:
                pass
