"""Safety net that turns stray Markdown into WhatsApp formatting (rule R-TONE-3).

The prompt is the first line of defence; this only fixes what slips through.
WhatsApp renders *bold*, _italic_ and plain lines, nothing else.
"""

import re

_RULES = [
    (re.compile(r"\*\*(.+?)\*\*"), r"*\1*"),  # **bold** -> *bold*
    (re.compile(r"__(.+?)__"), r"_\1_"),  # __italic__ -> _italic_
    (re.compile(r"\[([^\]]+)\]\((\S+?)\)"), r"\1 (\2)"),  # [text](url) -> text (url)
    (re.compile(r"^#{1,6}\s*(.+)$", re.M), r"*\1*"),  # "## Title" -> *Title*
    (re.compile(r"^\s*[-*]\s+", re.M), "• "),  # "- item" / "* item" -> "• item"
    (re.compile(r"^\s*\|?\s*:?-{3,}.*$\n?", re.M), ""),  # table separator rows
]


def sanitize(text: str) -> str:
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    text = "\n".join(_table_row(line) for line in text.splitlines())
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _table_row(line: str) -> str:
    """Flatten a Markdown table row: | Violão | R$ 599,90 | -> Violão — R$ 599,90."""
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return line
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return " — ".join(cell for cell in cells if cell)
