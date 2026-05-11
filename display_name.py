"""
Counterparty display name manager.
Maps raw truncated/messy counterparty names → clean display names.
Stored in display_name.json (gitignored, grows over time).

Manage via CLI:
    python cli.py alias add --raw "axb-XX774- MANISHMU" --clean "Self Transfer"
    python cli.py alias list
"""

import json
from pathlib import Path

DISPLAY_NAME_FILE = Path(__file__).parent / "display_name.json"


def _load() -> dict[str, str]:
    if not DISPLAY_NAME_FILE.exists():
        _save({})
    with open(DISPLAY_NAME_FILE) as f:
        return json.load(f)


def _save(display_names: dict[str, str]) -> None:
    DISPLAY_NAME_FILE.write_text(
        json.dumps(dict(sorted(display_names.items())), indent=2, ensure_ascii=False)
    )


def add_alias(raw: str, clean: str) -> None:
    """Map a raw counterparty name to a clean display name."""
    display_names = _load()
    display_names[raw] = clean
    _save(display_names)


def get_aliases() -> dict[str, str]:
    """Return all display names as {raw: clean}."""
    return _load()


def apply_alias(counterparty: str | None) -> str | None:
    """Return the clean display name for a counterparty, or the original if none exists."""
    if not counterparty:
        return counterparty
    display_names = _load()
    return display_names.get(counterparty, counterparty)
