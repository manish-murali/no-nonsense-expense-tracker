"""
Counterparty alias manager.
Maps raw truncated/messy counterparty names → clean display names.
Stored in aliases.json (gitignored, grows over time).

Manage via CLI:
    python cli.py alias add --raw "axb-XX774- MANISHMU" --clean "Self Transfer"
    python cli.py alias list
"""

import json
from pathlib import Path

ALIASES_FILE = Path(__file__).parent / "aliases.json"


def _load() -> dict[str, str]:
    if not ALIASES_FILE.exists():
        _save({})
    with open(ALIASES_FILE) as f:
        return json.load(f)


def _save(aliases: dict[str, str]) -> None:
    ALIASES_FILE.write_text(
        json.dumps(dict(sorted(aliases.items())), indent=2, ensure_ascii=False)
    )


def add_alias(raw: str, clean: str) -> None:
    """Map a raw counterparty name to a clean display name."""
    aliases = _load()
    aliases[raw] = clean
    _save(aliases)


def get_aliases() -> dict[str, str]:
    """Return all aliases as {raw: clean}."""
    return _load()


def apply_alias(counterparty: str | None) -> str | None:
    """Return the clean name for a counterparty, or the original if no alias exists."""
    if not counterparty:
        return counterparty
    aliases = _load()
    return aliases.get(counterparty, counterparty)
