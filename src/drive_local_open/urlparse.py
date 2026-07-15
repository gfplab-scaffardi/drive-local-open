from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

FOLDER_RE = re.compile(
    r"/folders/([a-zA-Z0-9_-]+)|"
    r"/file/d/([a-zA-Z0-9_-]+)|"
    r"[?&]id=([a-zA-Z0-9_-]+)|"
    r"/document/d/([a-zA-Z0-9_-]+)|"
    r"/spreadsheets/d/([a-zA-Z0-9_-]+)|"
    r"/presentation/d/([a-zA-Z0-9_-]+)|"
    r"/forms/d/([a-zA-Z0-9_-]+)"
)
MY_DRIVE_RE = re.compile(r"/drive/(?:u/\d+/)?my-drive(?:/|$)", re.I)
DRIVE_HOSTS = ("drive.google.com", "docs.google.com")


@dataclass(frozen=True)
class ParsedDriveUrl:
    raw: str
    item_id: str | None
    is_my_drive_root: bool
    is_drive_host: bool

    @property
    def is_openable(self) -> bool:
        return self.is_drive_host and (self.is_my_drive_root or bool(self.item_id))


def parse_drive_url(url: str) -> ParsedDriveUrl:
    url = (url or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    is_host = any(h in host for h in DRIVE_HOSTS)

    if not is_host:
        return ParsedDriveUrl(url, None, False, False)

    if MY_DRIVE_RE.search(path) or path.rstrip("/").endswith("/drive"):
        return ParsedDriveUrl(url, None, True, True)

    item_id = None
    m = FOLDER_RE.search(url)
    if m:
        for g in m.groups():
            if g:
                item_id = g
                break
    return ParsedDriveUrl(url, item_id, False, True)
