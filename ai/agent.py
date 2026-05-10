"""
AI agent for the expense tracker — two-step pipeline:
  1. Generate SQL from user question (via Ollama /api/chat)
  2. Run SQL against tracker.db (read-only)
  3. Generate natural-language answer from results (via Ollama /api/chat)

Config: ai_config.json (gitignored). Falls back to built-in defaults if absent.
Prompts: ai/prompts/*.txt (committed to git).
History: persisted to tracker.db via storage.db conversation functions.
"""

import json
import re
import sqlite3
from pathlib import Path

import httpx

from storage import db as _db

# ── Paths ─────────────────────────────────────────────────────────────

_HERE        = Path(__file__).parent
_CONFIG_PATH = _HERE.parent / "ai_config.json"
_PROMPTS_DIR = _HERE / "prompts"

_DEFAULTS: dict = {
    "model":       "gemma3:4b",
    "endpoint":    "http://localhost:11434",
    "temperature": 0.1,
    "timeout":     60,
}

# ── Exceptions ────────────────────────────────────────────────────────

class AIConfigError(Exception):
    """ai_config.json exists but is malformed JSON."""

class OllamaUnavailableError(Exception):
    """Ollama is not reachable or timed out."""

class UnsafeSQLError(Exception):
    """LLM produced SQL that is not a safe SELECT statement."""


# ── Agent ─────────────────────────────────────────────────────────────

class AIAgent:

    # Keywords that must not appear in generated SQL
    _FORBIDDEN = re.compile(
        r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA)\b',
        re.IGNORECASE,
    )

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path         = db_path
        self.config          = self._load_config()
        self._sys_sql        = (_PROMPTS_DIR / "system.txt").read_text()
        self._sql_tpl        = (_PROMPTS_DIR / "sql_gen.txt").read_text()
        self._ans_sys        = (_PROMPTS_DIR / "answer.txt").read_text()

        # In-memory conversation histories (capped at 10 messages each)
        self._sql_history:  list[dict] = []   # user/assistant for SQL generation
        self._chat_history: list[dict] = []   # user/assistant for answer generation

        # Active conversation id in DB (set by caller after init)
        self.conversation_id: int | None = None

    # ── Config ────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        cfg = dict(_DEFAULTS)
        if _CONFIG_PATH.exists():
            try:
                user = json.loads(_CONFIG_PATH.read_text())
                cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
            except json.JSONDecodeError as e:
                raise AIConfigError(f"ai_config.json is malformed: {e}") from e
        return cfg

    # ── Connection check ──────────────────────────────────────────────

    async def check_connection(self) -> tuple[bool, str]:
        """
        Ping Ollama and verify the configured model is pulled.
        Returns (True, model_name) or (False, error_message).
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.config['endpoint']}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                target = self.config["model"]
                if any(target in m for m in models):
                    return True, target
                return False, (
                    f"Model '{target}' not found. "
                    f"Run:  ollama pull {target}"
                )
        except httpx.ConnectError:
            return False, "Ollama not running. Start with:  ollama serve"
        except Exception as e:
            return False, f"Connection error: {e}"

    # ── Ollama /api/chat call ─────────────────────────────────────────

    async def _call_chat(self, messages: list[dict]) -> str:
        """POST to /api/chat (multi-turn). Returns the assistant content string."""
        payload = {
            "model":    self.config["model"],
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": self.config["temperature"]},
        }
        try:
            async with httpx.AsyncClient(timeout=self.config["timeout"]) as client:
                r = await client.post(
                    f"{self.config['endpoint']}/api/chat",
                    json=payload,
                )
                r.raise_for_status()
                return r.json()["message"]["content"]
        except httpx.ConnectError:
            raise OllamaUnavailableError("Ollama is not running.")
        except httpx.TimeoutException:
            raise OllamaUnavailableError(
                f"Ollama timed out after {self.config['timeout']}s."
            )
        except Exception as e:
            raise OllamaUnavailableError(f"Ollama call failed: {e}") from e

    # ── SQL safety ────────────────────────────────────────────────────

    def _extract_sql(self, raw: str) -> str:
        """Pull the SELECT statement out of the LLM response."""
        # Fenced code block first
        fence = re.search(r"```(?:sql)?\s*\n?(SELECT .+?)```", raw, re.DOTALL | re.IGNORECASE)
        if fence:
            return fence.group(1).strip()
        # First bare SELECT
        match = re.search(r"(SELECT\b.+)", raw, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).split("\n\n")[0].strip()
        raise UnsafeSQLError(f"No SELECT found in response: {raw[:200]}")

    def _validate_sql(self, sql: str) -> str:
        """Assert SELECT-only. Return cleaned SQL or raise UnsafeSQLError."""
        clean = sql.strip().rstrip(";").strip()
        if not clean.upper().startswith("SELECT"):
            raise UnsafeSQLError(f"Expected SELECT, got: {clean[:60]}")
        if self._FORBIDDEN.search(clean):
            raise UnsafeSQLError(f"Forbidden keyword in SQL: {clean[:100]}")
        return clean

    # ── DB context for prompt ─────────────────────────────────────────

    def _db_context(self) -> str:
        """Fetch live metadata from the DB to inject into the sql_gen prompt."""
        try:
            conn = sqlite3.connect(self.db_path or _db.get_db_path())
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")

            # Date range
            r = conn.execute(
                "SELECT MIN(date_iso) AS min_d, MAX(date_iso) AS max_d FROM savings_transactions"
            ).fetchone()
            date_range = f"{r['min_d']} to {r['max_d']}" if r and r['min_d'] else "unknown"

            # Accounts
            accounts = conn.execute(
                "SELECT account_name, account_type FROM accounts ORDER BY account_name"
            ).fetchall()
            acct_list = ", ".join(f"{a['account_name']} ({a['account_type']})" for a in accounts)

            # Top counterparties by spend
            top_cp = conn.execute("""
                SELECT COALESCE(alias_name, counterparty) AS name,
                       ROUND(SUM(debit), 0) AS total
                FROM savings_transactions
                WHERE direction='DEBIT' AND counterparty IS NOT NULL
                GROUP BY counterparty ORDER BY total DESC LIMIT 8
            """).fetchall()
            cp_list = ", ".join(f"{r['name']} (₹{int(r['total']):,})" for r in top_cp if r['name'])

            # Top credit sources
            top_cr = conn.execute("""
                SELECT COALESCE(alias_name, counterparty) AS name,
                       ROUND(SUM(credit), 0) AS total
                FROM savings_transactions
                WHERE direction='CREDIT' AND counterparty IS NOT NULL
                GROUP BY counterparty ORDER BY total DESC LIMIT 5
            """).fetchall()
            cr_list = ", ".join(f"{r['name']} (₹{int(r['total']):,})" for r in top_cr if r['name'])

            # Transaction count
            count = conn.execute("SELECT COUNT(*) FROM savings_transactions").fetchone()[0]
            conn.close()

            return (
                f"- Transactions in DB: {count} savings records\n"
                f"- Date range: {date_range}\n"
                f"- Accounts: {acct_list or 'none'}\n"
                f"- Top spend counterparties: {cp_list or 'none'}\n"
                f"- Top credit sources: {cr_list or 'none'}"
            )
        except Exception:
            return "- (context unavailable)"

    # ── DB execution ──────────────────────────────────────────────────

    def _run_sql(self, sql: str) -> list[dict]:
        """Execute validated SELECT. Returns up to 50 rows."""
        conn = sqlite3.connect(self.db_path or _db.get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")          # engine-level write guard
        conn.execute("PRAGMA case_sensitive_like = OFF") # case-insensitive LIKE
        try:
            rows = conn.execute(sql).fetchmany(50)
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── History helpers ───────────────────────────────────────────────

    def _trim(self, history: list[dict], max_msgs: int = 10) -> list[dict]:
        return history[-max_msgs:]

    def load_conversation(self, conv_id: int) -> list[dict]:
        """
        Rebuild in-memory histories from DB messages.
        Returns list of {role, content} for chat-log replay.
        """
        self.conversation_id = conv_id
        messages = _db.get_conversation_messages(conv_id, self.db_path)
        self._sql_history  = []
        self._chat_history = []

        for m in messages:
            role, content = m["role"], m["content"]
            if role == "user":
                self._chat_history.append({"role": "user",      "content": content})
                self._sql_history.append( {"role": "user",      "content": content})
            elif role == "assistant":
                self._chat_history.append({"role": "assistant", "content": content})
            elif role == "sql":
                self._sql_history.append( {"role": "assistant", "content": content})

        self._sql_history  = self._trim(self._sql_history)
        self._chat_history = self._trim(self._chat_history)
        return messages

    def reset(self) -> int:
        """Clear histories and create a new DB conversation. Returns new conv_id."""
        self._sql_history  = []
        self._chat_history = []
        new_id = _db.create_conversation(self.db_path)
        self.conversation_id = new_id
        return new_id

    # ── Main pipeline ─────────────────────────────────────────────────

    async def ask(self, question: str) -> dict:
        """
        Two-step pipeline:
          1. Generate SQL (with sql_history context)
          2. Run SQL
          3. Generate answer (with chat_history context)
          4. Persist all three messages to DB

        Returns:
          {answer, sql, rows, error}
        """
        result: dict = {"answer": "", "sql": "", "rows": [], "error": None}

        # ── Step 1: SQL generation ─────────────────────────────────
        system_sql = (
            self._sql_tpl
            .replace("{question}", question)
            .replace("{db_context}", self._db_context())
        )
        sql_messages = [
            {"role": "system", "content": system_sql},
            *self._trim(self._sql_history),
            {"role": "user", "content": question},
        ]
        try:
            raw_response = await self._call_chat(sql_messages)
        except OllamaUnavailableError as e:
            result["error"]  = str(e)
            result["answer"] = str(e)
            return result

        try:
            raw_sql  = self._extract_sql(raw_response)
            safe_sql = self._validate_sql(raw_sql)
            result["sql"] = safe_sql
        except UnsafeSQLError as e:
            result["error"]  = str(e)
            result["answer"] = (
                "I wasn't able to generate a valid query for that. "
                "Try rephrasing your question."
            )
            return result

        # Update sql history
        self._sql_history.append({"role": "user",      "content": question})
        self._sql_history.append({"role": "assistant", "content": safe_sql})
        self._sql_history = self._trim(self._sql_history)

        # ── Step 2: Run SQL ────────────────────────────────────────
        try:
            rows = self._run_sql(safe_sql)
            result["rows"] = rows
        except sqlite3.Error as e:
            result["error"]  = f"SQL error: {e}"
            result["answer"] = (
                "The query I generated had an error. "
                "Try rephrasing your question."
            )
            return result

        if not rows:
            result["answer"] = "I found no matching transactions for that question."
            # Still persist user question to history for context
            self._persist(question, safe_sql, result["answer"])
            return result

        # ── Step 3: Natural-language answer ───────────────────────
        rows_json = json.dumps(rows[:15], default=str, ensure_ascii=False)
        ans_user_content = f"{question}\n\nData:\n{rows_json}"

        ans_messages = [
            {"role": "system", "content": self._ans_sys},
            *self._trim(self._chat_history),
            {"role": "user", "content": ans_user_content},
        ]
        try:
            answer = (await self._call_chat(ans_messages)).strip()
        except OllamaUnavailableError as e:
            # SQL ran OK — give a raw fallback
            answer = (
                f"Query returned {len(rows)} result(s) but Ollama "
                f"is unavailable for the explanation: {e}"
            )
        result["answer"] = answer

        # Update chat history + persist
        self._chat_history.append({"role": "user",      "content": question})
        self._chat_history.append({"role": "assistant", "content": answer})
        self._chat_history = self._trim(self._chat_history)
        self._persist(question, safe_sql, answer)

        return result

    def _persist(self, question: str, sql: str, answer: str) -> None:
        """Save user/sql/assistant messages to the active conversation in DB."""
        if self.conversation_id is None:
            return
        try:
            _db.save_message(self.conversation_id, "user",      question, self.db_path)
            _db.save_message(self.conversation_id, "sql",       sql,      self.db_path)
            _db.save_message(self.conversation_id, "assistant", answer,   self.db_path)
        except Exception:
            pass  # persistence failure must never break the UI
