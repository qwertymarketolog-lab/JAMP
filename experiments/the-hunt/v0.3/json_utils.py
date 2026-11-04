"""Safe parsing helpers for model-produced JSON completions."""
from __future__ import annotations

import json
from typing import Any


def strip_markdown_json(content: str) -> str:
    """Remove a surrounding Markdown JSON code fence, when present."""
    text = content.strip()
    lines = text.splitlines()
    fence = "```"
    if len(lines) >= 3 and lines[0].strip().startswith(fence) and lines[-1].strip() == fence:
        language = lines[0].strip()[3:].strip().lower()
        if language in ("", "json"):
            return "\n".join(lines[1:-1]).strip()
    return text


def safe_parse_json(content: str) -> Any | None:
    """Parse JSON content and return None instead of raising on malformed input."""
    try:
        return json.loads(strip_markdown_json(content))
    except (json.JSONDecodeError, TypeError):
        return None
