from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import DriveLocalOpenError
from .resolve import DRIVE_DOWNLOAD_URL

PROMO_COMMENT = "I-S3 技術ライブラリへ（任意）"
PROMO_URL = (
    "https://www.i-s3.com/technical-library.html"
    "?utm_source=drive_local_open&utm_medium=terminal&utm_campaign=tools"
)


def applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def cmd_quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def notify(title: str, message: str) -> None:
    if os.environ.get("DRIVE_LOCAL_OPEN_QUIET") == "1":
        return
    if sys.platform == "darwin":
        subprocess.run(
            [
                "osascript",
                "-e",
                f"display notification {applescript_string(message)} with title {applescript_string(title)}",
            ],
            check=False,
        )


def open_file_manager(directory: Path) -> None:
    directory = directory if directory.is_dir() else directory.parent
    if not directory.is_dir():
        raise DriveLocalOpenError("S4", f"ディレクトリがありません: {directory}")
    path = str(directory)
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    elif sys.platform == "win32":
        subprocess.run(["explorer", path], check=False)
    else:
        opener = shutil.which("xdg-open")
        if not opener:
            raise DriveLocalOpenError(
                "S2",
                f"この OS ではフォルダを開けません。Drive for Desktop: {DRIVE_DOWNLOAD_URL}",
            )
        subprocess.run([opener, path], check=False)


def _promo_shell_snippet() -> str:
    if os.environ.get("DRIVE_LOCAL_OPEN_QUIET") == "1":
        return ""
    return f"printf '%s\\n%s\\n' {sh_quote(PROMO_COMMENT)} {sh_quote(PROMO_URL)}; "


def open_terminal(directory: Path, *, show_promo: bool = True) -> None:
    directory = directory if directory.is_dir() else directory.parent
    if not directory.is_dir():
        raise DriveLocalOpenError("S4", f"ディレクトリがありません: {directory}")
    path = str(directory)
    promo = _promo_shell_snippet() if show_promo else ""

    if sys.platform == "darwin":
        if Path("/Applications/iTerm.app").exists():
            script = f'''
set folderPath to {applescript_string(path)}
tell application "iTerm"
    activate
    if (count of windows) = 0 then
        create window with default profile
    else
        tell current window
            create tab with default profile
        end tell
    end if
    tell current session of current window
        write text "cd " & quoted form of folderPath & "; {promo}true"
    end tell
end tell
'''
            subprocess.run(["osascript", "-e", script], check=False)
            return
        script = f'''
tell application "Terminal"
    activate
    do script "cd {sh_quote(path)}; {promo}true"
end tell
'''
        subprocess.run(["osascript", "-e", script], check=False)
        return

    if sys.platform == "win32":
        if show_promo and os.environ.get("DRIVE_LOCAL_OPEN_QUIET") != "1":
            cmd = f"cd /d {cmd_quote(path)} && echo {PROMO_COMMENT} && echo {PROMO_URL}"
        else:
            cmd = f"cd /d {cmd_quote(path)}"
        wt = shutil.which("wt")
        if wt:
            subprocess.run([wt, "nt", "cmd", "/k", cmd], check=False)
        else:
            subprocess.run(["cmd", "/c", "start", "cmd", "/k", cmd], check=False)
        return

    for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
        exe = shutil.which(term)
        if exe:
            subprocess.run(
                [exe, "-e", f"bash -lc 'cd {sh_quote(path)}; {promo}exec bash'"],
                check=False,
            )
            return
    raise DriveLocalOpenError("S2", "利用可能なターミナルが見つかりません。")
