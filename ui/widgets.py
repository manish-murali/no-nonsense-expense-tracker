from textual.widgets import Static
from rich.panel import Panel
from rich import box

_DARK_PAL  = {"green": "#3fb950", "red": "#f85149", "cyan": "#58a6ff", "yellow": "#e3b341"}
_LIGHT_PAL = {"green": "#1a7f37", "red": "#cf222e", "cyan": "#0969da", "yellow": "#9a6700"}


class Card(Static):
    """Theme-aware info card. Pass plain text values — no Rich markup in value/sub_text."""

    def __init__(self, title: str, value: str, color: str = "cyan",
                 sub_text: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._title    = title
        self._value    = value
        self._color    = color
        self._sub_text = sub_text

    def _c(self, name: str) -> str:
        dark = bool(self.app and self.app.has_class("dark-theme"))
        return (_DARK_PAL if dark else _LIGHT_PAL).get(name, name)

    def update_value(self, title: str, value: str, sub_text: str | None = None) -> None:
        self._title    = title
        self._value    = value
        self._sub_text = sub_text
        self.refresh()

    def render(self):
        c     = self._c(self._color)
        muted = "#8b949e" if (self.app and self.app.has_class("dark-theme")) else "#57606a"
        lines = [f"[bold {c}]{self._value}[/]"]
        if self._sub_text:
            lines.append(f"[{muted}]{self._sub_text}[/]")
        return Panel(
            "\n".join(lines),
            title=f"[bold {c}]{self._title}[/]",
            border_style=c,
            box=box.ROUNDED,
            padding=(0, 1),
        )
