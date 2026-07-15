#!/usr/bin/env python3
"""Scenario fixtures for S1–S8, S10 (no live Drive mount required)."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(ROOT))

from drive_local_open.cli import main, unwrap_protocol_url  # noqa: E402
from drive_local_open.errors import DriveLocalOpenError  # noqa: E402
from drive_local_open.resolve import (  # noqa: E402
    DRIVE_DOWNLOAD_URL,
    drive_not_mounted_message,
    my_drive_path,
    nearest_existing_ancestor,
    resolve_via_metadata,
    resolve_via_shortcut,
)
from drive_local_open.urlparse import parse_drive_url  # noqa: E402


def _make_db(path: Path, script: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(script)
    con.commit()
    con.close()


SCHEMA = """
CREATE TABLE items (
  stable_id INTEGER PRIMARY KEY,
  id TEXT UNIQUE,
  trashed BOOLEAN NOT NULL DEFAULT 0,
  starred BOOLEAN NOT NULL DEFAULT 0,
  is_owner BOOLEAN NOT NULL DEFAULT 1,
  mime_type TEXT NOT NULL DEFAULT '',
  is_folder BOOLEAN NOT NULL,
  is_tombstone BOOLEAN NOT NULL DEFAULT 0,
  local_title TEXT,
  subscribed BOOLEAN NOT NULL DEFAULT 1
);
CREATE TABLE stable_parents (
  item_stable_id INTEGER NOT NULL,
  parent_stable_id INTEGER NOT NULL,
  local_title_hash INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(item_stable_id, parent_stable_id)
);
"""


class S1NotDriveUrl(unittest.TestCase):
    def test_parse(self):
        p = parse_drive_url("https://example.com/")
        self.assertFalse(p.is_openable)

    def test_cli_exit(self):
        code = main(["--quiet", "--print-only", "https://example.com/"])
        self.assertEqual(code, 1)


class S2DriveNotMounted(unittest.TestCase):
    def test_message_has_download_link(self):
        msg = drive_not_mounted_message()
        self.assertIn(DRIVE_DOWNLOAD_URL, msg)

    def test_cli_without_mount(self):
        with mock.patch("drive_local_open.cli.resolve_parsed") as resolve:
            resolve.side_effect = DriveLocalOpenError("S2", drive_not_mounted_message())
            code = main(
                ["--quiet", "--print-only", "https://drive.google.com/drive/folders/abc"]
            )
        self.assertEqual(code, 1)


class S3AmbiguousAccounts(unittest.TestCase):
    def test_note_when_same_id_on_two_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_a = Path(tmp) / "A"
            root_b = Path(tmp) / "B"
            for root in (root_a, root_b):
                bank = root / "マイドライブ" / "Bank"
                bank.mkdir(parents=True)
            db = Path(tmp) / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'rootMyDrive',1,'マイドライブ'),
                  (2,'idBank',1,'Bank');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES (2,1);
                """,
            )
            result = resolve_via_metadata([root_a, root_b], "idBank", db_path=db)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertIsNotNone(result.note)
            self.assertIn("S3", result.note or "")


class S4NotSyncedParentFallback(unittest.TestCase):
    def test_opens_parent_when_child_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank = root / "マイドライブ" / "Bank"
            bank.mkdir(parents=True)
            # Child listed in metadata but not on disk
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'rootMyDrive',1,'マイドライブ'),
                  (2,'idBank',1,'Bank'),
                  (3,'idChild',1,'MissingChild');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES
                  (2,1),(3,2);
                """,
            )
            result = resolve_via_metadata([root], "idChild", db_path=db)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.source, "parent_fallback")
            self.assertEqual(result.path.resolve(), bank.resolve())

    def test_no_fallback_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "マイドライブ" / "Bank").mkdir(parents=True)
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'rootMyDrive',1,'マイドライブ'),
                  (2,'idBank',1,'Bank'),
                  (3,'idChild',1,'MissingChild');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES
                  (2,1),(3,2);
                """,
            )
            result = resolve_via_metadata(
                [root], "idChild", db_path=db, allow_parent_fallback=False
            )
            self.assertIsNone(result)

    def test_nearest_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "a" / "b"
            parent.mkdir(parents=True)
            missing = parent / "c" / "d"
            found = nearest_existing_ancestor(missing, stop_at=root)
            self.assertEqual(found.resolve(), parent.resolve())


class S5SharedAndShortcut(unittest.TestCase):
    def test_shortcut_without_metadata_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "sharedXYZ"
            sc = root / ".shortcut-targets-by-id" / sid
            sc.mkdir(parents=True)
            result = resolve_via_shortcut([root], sid)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.source, "shortcut")

    def test_shared_drives_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "共有ドライブ" / "TeamDrive" / "Folder"
            shared.mkdir(parents=True)
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'sharedRoot',1,'共有ドライブ'),
                  (2,'team',1,'TeamDrive'),
                  (3,'folder',1,'Folder');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES
                  (2,1),(3,2);
                """,
            )
            result = resolve_via_metadata([root], "folder", db_path=db)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.path.resolve(), shared.resolve())


class S6FileParent(unittest.TestCase):
    def test_file_opens_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank = root / "マイドライブ" / "Bank"
            bank.mkdir(parents=True)
            f = bank / "note.txt"
            f.write_text("hi", encoding="utf-8")
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'rootMyDrive',1,'マイドライブ'),
                  (2,'idBank',1,'Bank'),
                  (3,'idFile',0,'note.txt');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES
                  (2,1),(3,2);
                """,
            )
            result = resolve_via_metadata([root], "idFile", db_path=db)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.path.resolve(), bank.resolve())


class S7MyDrive(unittest.TestCase):
    def test_parse_and_path(self):
        p = parse_drive_url("https://drive.google.com/drive/u/0/my-drive")
        self.assertTrue(p.is_my_drive_root)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            md = root / "マイドライブ"
            md.mkdir()
            self.assertEqual(my_drive_path(root), md)


class S8Tombstone(unittest.TestCase):
    def test_tombstone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "マイドライブ").mkdir()
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + """
                INSERT INTO items(stable_id,id,is_folder,local_title,is_tombstone) VALUES
                  (1,'dead',1,'Gone',1);
                """,
            )
            with self.assertRaises(DriveLocalOpenError) as ctx:
                resolve_via_metadata([root], "dead", db_path=db)
            self.assertEqual(ctx.exception.code, "S8")


class S9DbError(unittest.TestCase):
    def test_unreadable_db_raises_s9(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = Path(tmp) / "metadata_sqlite_db"
            bad.write_bytes(b"not a sqlite database")
            with self.assertRaises(DriveLocalOpenError) as ctx:
                resolve_via_metadata([root], "any", db_path=bad)
            self.assertEqual(ctx.exception.code, "S9")


class S10UnicodeNormalize(unittest.TestCase):
    def test_nfd_on_disk_nfc_in_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # On-disk NFD, metadata NFC (common on macOS)
            title_nfc = "サンプル"
            title_nfd = unicodedata.normalize("NFD", title_nfc)
            folder = root / "マイドライブ" / title_nfd
            folder.mkdir(parents=True)
            db = root / "metadata_sqlite_db"
            _make_db(
                db,
                SCHEMA
                + f"""
                INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
                  (1,'rootMyDrive',1,'マイドライブ'),
                  (2,'idSample',1,'{title_nfc}');
                INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES (2,1);
                """,
            )
            result = resolve_via_metadata([root], "idSample", db_path=db)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.path.exists())


class ProtocolAndDocs(unittest.TestCase):
    def test_protocol_unwrap(self):
        u = unwrap_protocol_url(
            "drive-local-open://open?url=https%3A%2F%2Fdrive.google.com%2Fdrive%2Ffolders%2Fabc"
        )
        self.assertEqual(u, "https://drive.google.com/drive/folders/abc")

    def test_docs_url(self):
        p = parse_drive_url("https://docs.google.com/document/d/abc123XYZ/edit")
        self.assertEqual(p.item_id, "abc123XYZ")


if __name__ == "__main__":
    unittest.main()
