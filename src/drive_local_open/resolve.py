from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    DriveLocalOpenError,
    S2_DRIVE_NOT_MOUNTED,
    S4_NOT_SYNCED,
    S8_TOMBSTONE,
    S9_DB_ERROR,
    S11_TIMEOUT,
)
from .urlparse import ParsedDriveUrl

XATTR_ITEM_ID = "com.google.drivefs.item-id#S"
SKIP_DIR_NAMES = {
    ".Trash",
    ".tmp",
    "content_cache",
    "Other computers",
    "Shared drives",
    "共有ドライブ",
}


@dataclass(frozen=True)
class ResolveResult:
    path: Path
    item_id: str | None
    is_my_drive_root: bool
    source: str  # metadata | shortcut | xattr | my_drive


def _home() -> Path:
    return Path.home()


def find_cloud_roots() -> list[Path]:
    """Return Google Drive mount roots for the current OS (best-effort)."""
    roots: list[Path] = []
    if sys.platform == "darwin":
        cloud = _home() / "Library" / "CloudStorage"
        if cloud.is_dir():
            roots.extend(sorted(cloud.glob("GoogleDrive-*")))
        link = _home() / "GoogleDrive"
        if link.exists():
            try:
                resolved = link.resolve()
                # Prefer the CloudStorage parent as root when link points at My Drive
                if resolved.name in {"マイドライブ", "My Drive"} and resolved.parent not in roots:
                    roots.insert(0, resolved.parent)
            except OSError:
                pass
    else:
        # Windows typical layouts
        for cand in (
            _home() / "Google Drive",
            _home() / "My Drive",
            Path(os.environ.get("USERPROFILE", str(_home()))) / "Google Drive",
        ):
            if cand.is_dir() and cand not in roots:
                roots.append(cand)
        # Letter drives that look like Drive mirrors (best-effort, no hang)
        for letter in "GHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:/")
            try:
                if root.exists() and (
                    (root / "My Drive").is_dir() or (root / "マイドライブ").is_dir()
                ):
                    roots.append(root)
            except OSError:
                continue

        local = Path(os.environ.get("LOCALAPPDATA", str(_home() / "AppData" / "Local")))
        # Sometimes user-facing mirror is only under DriveFS; keep metadata path separate
        _ = local

    # De-dupe while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        try:
            key = r.resolve()
        except OSError:
            key = r
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def find_metadata_dbs() -> list[Path]:
    cands: list[Path] = []
    if sys.platform == "darwin":
        base = _home() / "Library" / "Application Support" / "Google" / "DriveFS"
    else:
        base = Path(os.environ.get("LOCALAPPDATA", str(_home() / "AppData" / "Local"))) / "Google" / "DriveFS"
    if base.is_dir():
        cands = list(base.glob("*/metadata_sqlite_db"))
    cands.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return cands


def parent_chain(con: sqlite3.Connection, stable_id: int) -> list[str]:
    parts: list[str] = []
    cur = stable_id
    seen: set[int] = set()
    for _ in range(64):
        if cur in seen:
            break
        seen.add(cur)
        row = con.execute(
            "SELECT local_title FROM items WHERE stable_id = ?", (cur,)
        ).fetchone()
        if not row or row[0] is None:
            break
        parts.append(row[0])
        parent = con.execute(
            "SELECT parent_stable_id FROM stable_parents WHERE item_stable_id = ?",
            (cur,),
        ).fetchone()
        if not parent:
            break
        cur = parent[0]
    parts.reverse()
    return parts


def _norm_variants(s: str) -> list[str]:
    return list(dict.fromkeys([s, unicodedata.normalize("NFC", s), unicodedata.normalize("NFD", s)]))


def _joinpath_variants(root: Path, parts: list[str]) -> list[Path]:
    """Expand Unicode normalization variants for each path segment."""
    variants: list[Path] = [root]
    for part in parts:
        next_variants: list[Path] = []
        for base in variants:
            for name in _norm_variants(part):
                next_variants.append(base / name)
        # Cap explosion
        variants = list(dict.fromkeys(next_variants))[:32]
    return variants


def _exists(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return False


def my_drive_path(cloud_root: Path) -> Path:
    preferred = ("マイドライブ", "My Drive", "Google Drive")
    for name in preferred:
        for n in _norm_variants(name):
            cand = cloud_root / n
            if cand.is_dir():
                return cand
    try:
        for child in cloud_root.iterdir():
            if child.name.startswith("."):
                continue
            if child.name in SKIP_DIR_NAMES:
                continue
            if child.is_dir():
                return child
    except OSError:
        pass
    link = _home() / "GoogleDrive"
    if link.exists():
        return link.resolve()
    raise DriveLocalOpenError(
        S2_DRIVE_NOT_MOUNTED,
        "マイドライブのローカルパスが見つかりません。Google Drive for Desktop を確認してください。",
    )


def resolve_via_metadata(
    cloud_roots: list[Path],
    item_id: str,
    db_path: Path | None = None,
) -> ResolveResult | None:
    dbs = [db_path] if db_path else find_metadata_dbs()
    if not dbs:
        return None

    last_err: Exception | None = None
    for db in dbs:
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            last_err = exc
            continue
        try:
            row = con.execute(
                "SELECT stable_id, is_folder, is_tombstone FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if not row:
                continue
            stable_id, is_folder, is_tombstone = row
            if is_tombstone:
                raise DriveLocalOpenError(
                    S8_TOMBSTONE,
                    "このアイテムは削除済み、またはアクセスできません。",
                )
            parts = parent_chain(con, stable_id)
            if not parts:
                continue

            for cloud_root in cloud_roots:
                candidates: list[tuple[Path, str]] = []
                for start in range(len(parts)):
                    for cand in _joinpath_variants(cloud_root, parts[start:]):
                        candidates.append((cand, "metadata"))
                for shortcut_root in (
                    cloud_root / ".shortcut-targets-by-id" / item_id,
                    *(_joinpath_variants(cloud_root / ".shortcut-targets-by-id", [item_id])),
                ):
                    candidates.append((shortcut_root, "shortcut"))

                for cand, source in candidates:
                    if _exists(cand):
                        path = cand
                        if not is_folder and path.is_file():
                            path = path.parent
                        try:
                            path = path.resolve() if path.exists() else path
                        except OSError:
                            pass
                        return ResolveResult(path, item_id, False, source)
        except DriveLocalOpenError:
            raise
        except sqlite3.Error as exc:
            last_err = exc
        finally:
            con.close()

    if last_err is not None and not dbs:
        raise DriveLocalOpenError(S9_DB_ERROR, f"Drive メタデータを読めませんでした: {last_err}")
    return None


def resolve_via_xattr_walk(
    cloud_roots: list[Path],
    item_id: str,
    *,
    max_entries: int = 50_000,
    timeout_sec: float = 3.0,
) -> ResolveResult | None:
    if sys.platform != "darwin":
        return None
    start = time.monotonic()
    count = 0
    for cloud_root in cloud_roots:
        for dirpath, dirnames, filenames in os.walk(cloud_root):
            if time.monotonic() - start > timeout_sec:
                raise DriveLocalOpenError(
                    S11_TIMEOUT,
                    "ローカル検索がタイムアウトしました。Drive の同期状態を確認して再試行してください。",
                )
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            base = Path(dirpath)
            for name in list(dirnames) + filenames:
                path = base / name
                count += 1
                if count > max_entries:
                    return None
                try:
                    value = subprocess.check_output(
                        ["xattr", "-p", XATTR_ITEM_ID, str(path)],
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=0.5,
                    ).strip()
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                    continue
                if value == item_id:
                    if path.is_file():
                        path = path.parent
                    return ResolveResult(path, item_id, False, "xattr")
    return None


def resolve_parsed(parsed: ParsedDriveUrl) -> ResolveResult:
    roots = find_cloud_roots()
    if not roots:
        raise DriveLocalOpenError(
            S2_DRIVE_NOT_MOUNTED,
            "Google Drive for Desktop のマウントが見つかりません。インストールとサインインを確認してください。",
        )

    if parsed.is_my_drive_root:
        return ResolveResult(my_drive_path(roots[0]), None, True, "my_drive")

    assert parsed.item_id
    try:
        result = resolve_via_metadata(roots, parsed.item_id)
    except DriveLocalOpenError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface as S9
        raise DriveLocalOpenError(S9_DB_ERROR, f"Drive メタデータ参照に失敗しました: {exc}") from exc

    if result is not None:
        return result

    try:
        result = resolve_via_xattr_walk(roots, parsed.item_id)
    except DriveLocalOpenError:
        raise
    except Exception:
        result = None

    if result is not None:
        return result

    raise DriveLocalOpenError(
        S4_NOT_SYNCED,
        "ローカルに同期されたフォルダが見つかりません。"
        " Google Drive for Desktop で同期されているか確認してください。",
    )
