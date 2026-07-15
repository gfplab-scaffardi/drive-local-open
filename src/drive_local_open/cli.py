from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

from .errors import (
    DriveLocalOpenError,
    S1_NOT_DRIVE_URL,
    S12_NO_URL,
)
from .openers import notify, open_file_manager, open_terminal
from .resolve import resolve_parsed
from .urlparse import parse_drive_url


def unwrap_protocol_url(value: str) -> str:
    """Accept drive-local-open://open?url=... from bookmarklets."""
    raw = (value or "").strip()
    if not raw.startswith("drive-local-open:"):
        return raw
    parsed = urllib.parse.urlparse(raw)
    qs = urllib.parse.parse_qs(parsed.query)
    if qs.get("url"):
        return qs["url"][0]
    if "url=" in raw:
        return urllib.parse.unquote(raw.split("url=", 1)[1].split("&", 1)[0])
    return raw


def chrome_active_url() -> str:
    if sys.platform == "darwin":
        script = r'''
tell application "Google Chrome"
    if (count of windows) is 0 then return ""
    return URL of active tab of front window
end tell
'''
        try:
            return subprocess.check_output(["osascript", "-e", script], text=True).strip()
        except subprocess.CalledProcessError as exc:
            raise DriveLocalOpenError(
                S12_NO_URL,
                f"Chrome の URL を取得できませんでした（オートメーション許可を確認）: {exc}",
            ) from exc
    if sys.platform == "win32":
        # COM automation is fragile; prefer explicit URL argument / extension.
        raise DriveLocalOpenError(
            S12_NO_URL,
            "Windows では URL を引数で渡してください（ブックマークレットまたは拡張を使用）。",
        )
    raise DriveLocalOpenError(S12_NO_URL, "この環境では Chrome URL の自動取得に対応していません。")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="drive-local-open",
        description="Google Drive の URL から、同期済みローカルフォルダを開きます（無料・データはPC内のみ）。",
    )
    p.add_argument("url", nargs="?", help="drive.google.com / docs.google.com の URL")
    p.add_argument(
        "--open",
        choices=("files", "terminal", "both", "none"),
        default="files",
        help="files=Finder/Explorer（既定）, terminal=ターミナル, both=両方, none=開かない",
    )
    p.add_argument("--print-only", action="store_true", help="解決したパスだけ表示")
    p.add_argument("--no-notify", action="store_true", help="通知を出さない")
    p.add_argument("--no-promo", action="store_true", help="ターミナルの2行リンクを出さない")
    p.add_argument("--quiet", action="store_true", help="通知もプロモも出さない（DRIVE_LOCAL_OPEN_QUIET=1 と同じ）")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.quiet:
        os.environ["DRIVE_LOCAL_OPEN_QUIET"] = "1"

    try:
        url = unwrap_protocol_url((args.url or "").strip())
        if not url:
            url = chrome_active_url()
        if not url:
            raise DriveLocalOpenError(S12_NO_URL, "URL が空です。Drive のタブで実行するか URL を渡してください。")

        parsed = parse_drive_url(url)
        if not parsed.is_drive_host:
            raise DriveLocalOpenError(
                S1_NOT_DRIVE_URL,
                "このタブは Google Drive / Docs の URL ではありません。",
            )
        if not parsed.is_openable:
            raise DriveLocalOpenError(
                S1_NOT_DRIVE_URL,
                "フォルダまたはファイルの ID を含む Drive / Docs URL を開いてください。",
            )

        result = resolve_parsed(parsed)
        path = result.path

        if args.print_only or args.open == "none":
            print(path)
            return 0

        if args.open in ("files", "both"):
            open_file_manager(path)
        if args.open in ("terminal", "both"):
            open_terminal(path, show_promo=not args.no_promo)

        print(path)
        if not args.no_notify and not args.quiet:
            notify("Drive Local Open", str(path))
        return 0
    except DriveLocalOpenError as exc:
        if not args.no_notify and not args.quiet:
            notify("Drive Local Open", exc.message)
        print(f"[{exc.code}] {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0)
