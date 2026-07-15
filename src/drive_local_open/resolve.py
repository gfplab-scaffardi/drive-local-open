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
DRIVE_DOWNLOAD_URL = "https://www.google.com/drive/download/"
SKIP_DIR_NAMES = {
    ".Trash",
    ".tmp",
    "content_cache",
    "Other computers",
}
# xattr 全面 walk では巨大になりやすいので後段で別予算を使う
SHARED_DIR_NAMES = {"Shared drives", "共有ドライブ"}


@dataclass(frozen=True)
class ResolveResult:
    path: Path
    item_id: str | None
    is_my_drive_root: bool
    source: str  # metadata | shortcut | xattr | my_drive | parent_fallback | shared
    note: str | None = None


def _home() -> Path:
    return Path.home()


def drive_not_mounted_message() -> str:
    return (
        "Google Drive for Desktop のマウントが見つかりません。"
        f" インストールとサインインを確認してください: {DRIVE_DOWNLOAD_URL}"
    )


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
        for cand in (
            _home() / "Google Drive",
            _home() / "My Drive",
            Path(os.environ.get("USERPROFILE", str(_home()))) / "Google Drive",
        ):
            if cand.is_dir() and cand not in roots:
                roots.append(cand)
        for letter in "GHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:/")
            try:
                if root.exists() and (
                    (root / "My Drive").is_dir() or (root / "マイドライブ").is_dir()
                ):
                    roots.append(root)
            except OSError:
                continue

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
        variants = list(dict.fromkeys(next_variants))[:32]
    return variants


def _exists(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return False


def _finalize_path(path: Path, *, is_folder: bool) -> Path:
    if not is_folder and path.is_file():
        path = path.parent
    try:
        return path.resolve() if path.exists() else path
    except OSError:
        return path


def shared_drive_roots(cloud_root: Path) -> list[Path]:
    roots: list[Path] = []
    for name in SHARED_DIR_NAMES:
        for n in _norm_variants(name):
            cand = cloud_root / n
            if cand.is_dir() and cand not in roots:
                roots.append(cand)
    return roots


def shortcut_candidates(cloud_root: Path, item_id: str) -> list[Path]:
    out: list[Path] = []
    base = cloud_root / ".shortcut-targets-by-id"
    out.append(base / item_id)
    out.extend(_joinpath_variants(base, [item_id]))
    return list(dict.fromkeys(out))


def nearest_existing_ancestor(path: Path, stop_at: Path | None = None) -> Path | None:
    """Walk up until an existing directory is found (inclusive of parents only)."""
    try:
        cur = path if path.is_dir() and _exists(path) else path.parent
    except OSError:
        cur = path.parent
    stop = None
    if stop_at is not None:
        try:
            stop = stop_at.resolve()
        except OSError:
            stop = stop_at
    for _ in range(64):
        if not _exists(cur):
            parent = cur.parent
            if parent == cur:
                return None
            cur = parent
            continue
        if cur.is_dir():
            try:
                resolved = cur.resolve()
            except OSError:
                resolved = cur
            if stop is not None and resolved == stop:
                return cur
            if stop is not None:
                try:
                    resolved.relative_to(stop)
                except ValueError:
                    return None
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent
    return None


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
            if child.name in SKIP_DIR_NAMES or child.name in SHARED_DIR_NAMES:
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
        "マイドライブのローカルパスが見つかりません。"
        f" Google Drive for Desktop を確認してください: {DRIVE_DOWNLOAD_URL}",
    )


def resolve_via_shortcut(cloud_roots: list[Path], item_id: str) -> ResolveResult | None:
    matches: list[ResolveResult] = []
    for cloud_root in cloud_roots:
        for cand in shortcut_candidates(cloud_root, item_id):
            if _exists(cand):
                path = _finalize_path(cand, is_folder=True)
                source = "shortcut"
                matches.append(ResolveResult(path, item_id, False, source))
                break
    if not matches:
        return None
    note = None
    if len(matches) > 1:
        note = (
            f"複数アカウントで一致（S3）。最初のマウントを採用: {matches[0].path}"
            f"（他 {len(matches) - 1} 件）"
        )
    return ResolveResult(
        matches[0].path,
        item_id,
        False,
        matches[0].source,
        note,
    )


def resolve_via_metadata(
    cloud_roots: list[Path],
    item_id: str,
    db_path: Path | None = None,
    *,
    allow_parent_fallback: bool = True,
) -> ResolveResult | None:
    dbs = [db_path] if db_path else find_metadata_dbs()
    if not dbs:
        return None

    last_err: Exception | None = None
    query_ok = False
    exact_matches: list[ResolveResult] = []
    parent_matches: list[ResolveResult] = []

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
            query_ok = True
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
                join_specs: list[tuple[Path, list[str], str]] = [
                    (cloud_root, parts, "metadata"),
                ]
                for shared_root in shared_drive_roots(cloud_root):
                    join_specs.append((shared_root, parts, "shared"))
                    if parts and parts[0] in SHARED_DIR_NAMES:
                        join_specs.append((shared_root, parts[1:], "shared"))

                candidates: list[tuple[Path, str]] = []
                for join_root, join_parts, source in join_specs:
                    if not join_parts:
                        candidates.append((join_root, source))
                        continue
                    for start in range(len(join_parts)):
                        for cand in _joinpath_variants(join_root, join_parts[start:]):
                            candidates.append((cand, source))
                for sc in shortcut_candidates(cloud_root, item_id):
                    candidates.append((sc, "shortcut"))

                seen_cand: set[str] = set()
                for cand, source in candidates:
                    key = str(cand)
                    if key in seen_cand:
                        continue
                    seen_cand.add(key)
                    if _exists(cand):
                        path = _finalize_path(cand, is_folder=bool(is_folder))
                        exact_matches.append(
                            ResolveResult(path, item_id, False, source)
                        )
                    elif allow_parent_fallback:
                        ancestor = nearest_existing_ancestor(cand, stop_at=cloud_root)
                        if ancestor is not None:
                            parent_matches.append(
                                ResolveResult(
                                    ancestor,
                                    item_id,
                                    False,
                                    "parent_fallback",
                                    "対象は未同期の可能性があるため、存在する親フォルダを開きます。",
                                )
                            )
        except DriveLocalOpenError:
            raise
        except sqlite3.Error as exc:
            last_err = exc
        finally:
            con.close()

    if not query_ok and last_err is not None:
        raise DriveLocalOpenError(
            S9_DB_ERROR,
            f"Drive メタデータを読めませんでした（Drive 再起動後に再試行）: {last_err}",
        )

    def _pick(matches: list[ResolveResult]) -> ResolveResult | None:
        if not matches:
            return None
        deduped: list[ResolveResult] = []
        seen: set[Path] = set()
        for m in matches:
            try:
                key = m.path.resolve()
            except OSError:
                key = m.path
            if key in seen:
                continue
            seen.add(key)
            deduped.append(m)
        note = deduped[0].note
        if len(deduped) > 1:
            s3 = (
                f"複数アカウントで一致（S3）。最初のマウントを採用: {deduped[0].path}"
                f"（他 {len(deduped) - 1} 件）"
            )
            note = f"{note} / {s3}" if note else s3
        m = deduped[0]
        return ResolveResult(m.path, m.item_id, m.is_my_drive_root, m.source, note)

    picked = _pick(exact_matches)
    if picked is not None:
        return picked
    return _pick(parent_matches)


def resolve_via_xattr_walk(
    cloud_roots: list[Path],
    item_id: str,
    *,
    max_entries: int = 50_000,
    timeout_sec: float = 3.0,
    include_shared: bool = False,
) -> ResolveResult | None:
    if sys.platform != "darwin":
        return None
    start = time.monotonic()
    count = 0
    skip = set(SKIP_DIR_NAMES)
    if not include_shared:
        skip |= SHARED_DIR_NAMES

    for cloud_root in cloud_roots:
        for dirpath, dirnames, filenames in os.walk(cloud_root):
            if time.monotonic() - start > timeout_sec:
                raise DriveLocalOpenError(
                    S11_TIMEOUT,
                    "ローカル検索がタイムアウトしました。Drive の同期状態を確認して再試行してください。",
                )
            dirnames[:] = [d for d in dirnames if d not in skip]
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
                    source = "shared" if any(p in SHARED_DIR_NAMES for p in path.parts) else "xattr"
                    return ResolveResult(path, item_id, False, source)
    return None


def resolve_parsed(
    parsed: ParsedDriveUrl,
    *,
    allow_parent_fallback: bool = True,
) -> ResolveResult:
    roots = find_cloud_roots()
    if not roots:
        raise DriveLocalOpenError(S2_DRIVE_NOT_MOUNTED, drive_not_mounted_message())

    if parsed.is_my_drive_root:
        return ResolveResult(my_drive_path(roots[0]), None, True, "my_drive")

    assert parsed.item_id
    item_id = parsed.item_id

    try:
        result = resolve_via_metadata(
            roots, item_id, allow_parent_fallback=allow_parent_fallback
        )
    except DriveLocalOpenError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface as S9
        raise DriveLocalOpenError(
            S9_DB_ERROR,
            f"Drive メタデータ参照に失敗しました（Drive 再起動後に再試行）: {exc}",
        ) from exc

    if result is not None:
        return result

    result = resolve_via_shortcut(roots, item_id)
    if result is not None:
        return result

    try:
        result = resolve_via_xattr_walk(roots, item_id, include_shared=False, timeout_sec=3.0)
    except DriveLocalOpenError:
        raise
    except Exception:
        result = None

    if result is not None:
        return result

    # S5: 共有ドライブは短時間だけ追加探索
    try:
        result = resolve_via_xattr_walk(
            roots, item_id, include_shared=True, timeout_sec=1.5, max_entries=20_000
        )
    except DriveLocalOpenError:
        # 共有探索のタイムアウトは致命にせず未同期へ
        result = None
    except Exception:
        result = None

    if result is not None:
        return result

    raise DriveLocalOpenError(
        S4_NOT_SYNCED,
        "ローカルに同期されたフォルダが見つかりません。"
        " Google Drive for Desktop で同期（オフライン可用）してから再試行してください。",
    )
