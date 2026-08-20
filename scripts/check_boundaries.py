#!/usr/bin/env python3
"""Fail CI if Studio regains a CLI or durable-file parsing boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1] / "agora_studio"
FORBIDDEN = (
    "AgoraCliBoundary",
    "subprocess",
    "._cli",
    "_gate_blockers",
    "parse_front_matter",
    'Path(".agora")',
    "shell=True",
)


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".js", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                failures.append(f"{path.relative_to(ROOT.parent)}: forbidden token {token!r}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("Application-service boundary check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
