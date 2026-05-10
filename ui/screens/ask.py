"""
Ask AI screen — Ollama + local model (default: gemma3:4b).

Two-step pipeline:
  1. User question → SQL (via /api/chat with conversation context)
  2. SQL results  → natural-language answer (via /api/chat)

Conversation history is persisted to tracker.db and reloaded on mount.
Config: ai_config.json (gitignored). Prompts: ai/prompts/*.txt (committed).
"""

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Input, Button, RichLog

from storage import db
from ui.widgets import Card


class AskTab(Vertical):

    def compose(self) -> ComposeResult:
        yield Static("\n [bold cyan]● Ask AI — Powered by Ollama (local · private)[/]\n")
        with Horizontal(id="model-info"):
            yield Card("Model",       "—",                         color="cyan",   classes="info-card", id="model-card")
            yield Card("Status",      "Checking…",                 color="yellow", classes="info-card", id="status-card")
            yield Card("Mode",        "SQL-first · 100% local",    color="green",  classes="info-card")

        self._chat_log = RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
        yield self._chat_log

        yield Static("", id="sql-disclosure")

        with Horizontal(id="chat-input-row"):
            yield Input(placeholder="Connect LLM to start typing…",
                        id="chat-input", disabled=True)
            yield Button("Send",  id="btn-send",  variant="primary", disabled=True)
            yield Button("Clear", id="btn-clear", variant="default", disabled=True)

        yield Static(
            "\n [dim]Examples:  How much did I spend on Zomato?  ·  "
            "What's my biggest expense this month?  ·  "
            "Compare Feb vs March spending  ·  What is my current balance?[/]\n"
        )

    # ── Mount ─────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._agent = None
        self._busy  = False

        self._chat_log.write(
            f"\n [bold yellow]System[/]  {_ts()}\n"
            " [dim]Checking Ollama connection…[/]\n"
        )
        self.run_worker(self._init_agent, exclusive=True)

    # ── Init agent + restore last conversation ────────────────────────

    async def _init_agent(self) -> None:
        from ai.agent import AIAgent, AIConfigError

        try:
            agent = AIAgent()
        except AIConfigError as e:
            self._chat_log.write(
                f"\n [bold red]Error[/]  {_ts()}\n"
                f" ai_config.json is malformed: {e}\n"
            )
            return

        ok, msg = await agent.check_connection()

        model_card  = self.query_one("#model-card",  Card)
        status_card = self.query_one("#status-card", Card)

        if ok:
            model_card.update_value("Model", agent.config["model"])
            model_card._color = "cyan"
            model_card.refresh()

            status_card.update_value("Status", "Connected ✓")
            status_card._color = "green"
            status_card.refresh()

            self._agent = agent
            self._enable_input(True)

            # Restore last conversation from DB
            conv_id = db.get_last_conversation_id()
            if conv_id is not None:
                messages = agent.load_conversation(conv_id)
                if messages:
                    self._chat_log.write(
                        f"\n [bold yellow]System[/]  {_ts()}\n"
                        f" [dim]Restoring previous conversation ({len(messages) // 3} exchange(s))…[/]\n"
                    )
                    for m in messages:
                        if m["role"] == "user":
                            self._append("user", m["content"])
                        elif m["role"] == "assistant":
                            self._append("assistant", m["content"])
                        elif m["role"] == "sql":
                            self._show_sql(m["content"])
                else:
                    self._chat_log.write(
                        f"\n [bold green]System[/]  {_ts()}\n"
                        f" Connected — {msg}. Ready!\n"
                    )
            else:
                # First ever launch — create a conversation
                agent.conversation_id = db.create_conversation()
                self._chat_log.write(
                    f"\n [bold green]System[/]  {_ts()}\n"
                    f" Connected — {msg}. Ask me anything about your transactions!\n"
                )
        else:
            status_card.update_value("Status", "Not connected")
            status_card._color = "yellow"
            status_card.refresh()

            model_card.update_value("Model", agent.config["model"])
            model_card.refresh()

            self._chat_log.write(
                f"\n [bold yellow]System[/]  {_ts()}\n"
                f" {msg}\n"
                " [dim]Input is disabled until Ollama is available.[/]\n"
            )

    # ── Send / respond ────────────────────────────────────────────────

    def _send(self) -> None:
        if self._busy or not self._agent:
            return
        inp      = self.query_one("#chat-input", Input)
        question = inp.value.strip()
        if not question:
            return
        inp.value = ""
        self._append("user", question)
        self._busy = True
        self._set_thinking(True)
        self.run_worker(self._respond(question), exclusive=True)

    async def _respond(self, question: str) -> None:
        try:
            result = await self._agent.ask(question)

            if result.get("sql"):
                self._show_sql(result["sql"])

            self._append("assistant", result["answer"])

            if result.get("error"):
                self._chat_log.write(
                    f" [dim red]↳ {result['error']}[/]\n"
                )
        except Exception as e:
            self._append("system", f"[bold red]Error:[/] {e}")
        finally:
            self._busy = False
            self._set_thinking(False)

    # ── Clear conversation ────────────────────────────────────────────

    def _clear(self) -> None:
        if not self._agent:
            return
        new_id = self._agent.reset()
        self._chat_log.clear()
        self.query_one("#sql-disclosure", Static).update("")
        self._chat_log.write(
            f"\n [bold yellow]System[/]  {_ts()}\n"
            f" New conversation started. Ask me anything!\n"
        )

    # ── Button / input events ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-send":
            self._send()
        elif event.button.id == "btn-clear":
            self._clear()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self._send()

    # ── UI helpers ────────────────────────────────────────────────────

    def _enable_input(self, enabled: bool) -> None:
        inp = self.query_one("#chat-input", Input)
        inp.disabled    = not enabled
        inp.placeholder = (
            "Ask anything about your transactions…"
            if enabled else
            "Connect LLM to start typing…"
        )
        self.query_one("#btn-send",  Button).disabled = not enabled
        self.query_one("#btn-clear", Button).disabled = not enabled

    def _set_thinking(self, thinking: bool) -> None:
        btn = self.query_one("#btn-send", Button)
        btn.disabled  = thinking
        btn.label     = "…" if thinking else "Send"
        self.query_one("#chat-input", Input).disabled = thinking

    def _show_sql(self, sql: str) -> None:
        oneliner = " ".join(sql.split())
        self.query_one("#sql-disclosure", Static).update(
            f" [dim]SQL → [cyan]{oneliner}[/][/]\n"
        )

    def _append(self, role: str, message: str) -> None:
        ts = _ts()
        if role == "user":
            self._chat_log.write(f"\n [bold cyan]You[/]  {ts}")
            self._chat_log.write(f" [on #1e3a5f] {message} [/]\n")
        elif role == "assistant":
            self._chat_log.write(f"\n [bold yellow]Gemma[/]  {ts}")
            self._chat_log.write(f" {message}\n")
        else:  # system
            self._chat_log.write(f"\n [dim]{message}[/]\n")


def _ts() -> str:
    return datetime.now().strftime("%H:%M")
