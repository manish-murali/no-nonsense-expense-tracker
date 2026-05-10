from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static, DataTable
from rich.text import Text

from storage import db


class MerchantDetail(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("", id="md-header")
        yield DataTable(id="md-table", zebra_stripes=True, cursor_type="none")

    def show(self, merchant: str) -> None:
        rows = db.get_merchant_transactions(merchant)
        total = sum(r["debit"] or r["credit"] or 0 for r in rows)

        self.query_one("#md-header", Static).update(
            f"\n [bold cyan]● {merchant}[/]"
            f"  [dim]— {len(rows)} transactions · Total ₹{total:,.2f}[/]\n"
        )
        table = self.query_one("#md-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Account", "Type", "Dir", "Debit", "Credit", "UPI ID", "Cpty Bank")
        for r in rows:
            dir_text = Text("↑ IN", style="green") if r["direction"] == "CREDIT" else Text("↓ OUT", style="red")
            table.add_row(
                r["date"], r["account_name"], r["transaction_type"], dir_text,
                f"₹{r['debit']:,.2f}"  if r["debit"]  else "—",
                f"₹{r['credit']:,.2f}" if r["credit"] else "—",
                r["upi_id"]            or "—",
                r["counterparty_bank"] or "—",
            )
        self.display = True

    def hide(self) -> None:
        self.display = False


class ExpensesTab(ScrollableContainer):

    def compose(self) -> ComposeResult:
        yield Static("\n [bold cyan]● Expenses by Category[/]\n")
        yield Static("", id="cat-chart")

        yield Static("\n [bold cyan]● Top 10 Merchants[/]  [dim]Click a row to see transactions[/]\n")
        yield DataTable(id="merchant-table", zebra_stripes=True, cursor_type="row")

        detail = MerchantDetail(id="merchant-detail")
        detail.display = False
        yield detail

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._load_categories()
        self._load_merchants()

    def _load_categories(self) -> None:
        rows    = db.get_category_breakdown()
        chart   = self.query_one("#cat-chart", Static)
        if not rows:
            chart.update("  [dim]No data yet.[/]")
            return
        max_amt = max(r["total_spent"] or 0 for r in rows) or 1
        lines   = []
        for r in rows:
            amt = r["total_spent"] or 0
            bar = "█" * int((amt / max_amt) * 25)
            lines.append(
                f"  {r['category']:<22} [yellow]{bar:<25}[/] "
                f"₹{amt:>10,.2f}  [dim]{r['txn_count']} txns[/]"
            )
        chart.update("\n".join(lines))

    def _load_merchants(self) -> None:
        table = self.query_one("#merchant-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Merchant", "Total Spent", "Transactions", "Avg per Txn")
        for i, r in enumerate(db.get_top_merchants(10), 1):
            avg = (r["total_spent"] or 0) / max(r["txn_count"], 1)
            table.add_row(
                str(i),
                r["counterparty"] or "—",
                f"₹{r['total_spent']:,.2f}" if r["total_spent"] else "—",
                str(r["txn_count"]),
                f"₹{avg:,.2f}",
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "merchant-table":
            return
        table    = self.query_one("#merchant-table", DataTable)
        detail   = self.query_one("#merchant-detail", MerchantDetail)
        merchant = str(table.get_cell_at((event.cursor_row, 1)))
        detail.show(merchant)
        self.scroll_end(animate=True)
