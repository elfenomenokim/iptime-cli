"""Plain-text tables that line up with Korean (double-width) text."""
from __future__ import annotations

import unicodedata


def width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text: str, size: int) -> str:
    return text + " " * (size - width(text))


def table(headers: list, rows: list) -> str:
    cells = [[("" if c is None else str(c)) for c in row] for row in rows]
    sizes = [max([width(h)] + [width(r[i]) for r in cells]) for i, h in enumerate(headers)]
    lines = ["  ".join(pad(h, sizes[i]) for i, h in enumerate(headers)).rstrip()]
    lines += ["  ".join(pad(c, sizes[i]) for i, c in enumerate(r)).rstrip() for r in cells]
    return "\n".join(lines)


def pairs(items: list) -> str:
    """Two-column key/value block."""
    size = max(width(k) for k, _ in items)
    return "\n".join(f"{pad(k, size)}  {'' if v is None else v}" for k, v in items)


def human_bytes(n) -> str:
    if n is None:
        return ""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def human_duration(seconds) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = [f"{d}d" if d else "", f"{h}h" if h or d else "", f"{m}m" if (m or h or d) else "",
             f"{s}s" if not (d or h) else ""]
    return " ".join(p for p in parts if p) or "0s"
