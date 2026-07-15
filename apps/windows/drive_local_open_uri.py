#!/usr/bin/env python3
"""Windows URL-scheme shim: drive-local-open://open?url=... -> CLI."""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(ROOT))

from drive_local_open.cli import main  # noqa: E402


def unwrap(arg: str) -> str:
    if arg.startswith("drive-local-open:"):
        parsed = urllib.parse.urlparse(arg)
        qs = urllib.parse.parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return qs["url"][0]
        # path form drive-local-open://open?url=
        if parsed.path and "url=" in arg:
            return urllib.parse.unquote(arg.split("url=", 1)[1].split("&", 1)[0])
    return arg


def main_win(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    out: list[str] = []
    for a in args:
        if a.startswith("drive-local-open:"):
            out.append(unwrap(a))
        else:
            out.append(a)
    if "--open" not in out:
        out = ["--open", "files", *out]
    return main(out)


if __name__ == "__main__":
    raise SystemExit(main_win())
