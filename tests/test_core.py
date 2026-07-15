#!/usr/bin/env python3
"""Unit tests that do not require a live Drive mount."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from drive_local_open.errors import DriveLocalOpenError  # noqa: E402
from drive_local_open.urlparse import parse_drive_url  # noqa: E402
from drive_local_open.resolve import my_drive_path, resolve_via_metadata  # noqa: E402
import sqlite3  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_s1_not_drive(self):
        p = parse_drive_url("https://example.com/")
        self.assertFalse(p.is_drive_host)
        self.assertFalse(p.is_openable)

    def test_folder(self):
        p = parse_drive_url("https://drive.google.com/drive/folders/0BztHi9eQmhGueHBKWlZmSDFVMTg")
        self.assertTrue(p.is_openable)
        self.assertEqual(p.item_id, "0BztHi9eQmhGueHBKWlZmSDFVMTg")

    def test_my_drive(self):
        p = parse_drive_url("https://drive.google.com/drive/u/0/my-drive")
        self.assertTrue(p.is_my_drive_root)
        self.assertTrue(p.is_openable)

    def test_docs_file(self):
        p = parse_drive_url("https://docs.google.com/document/d/abc123XYZ/edit")
        self.assertEqual(p.item_id, "abc123XYZ")

    def test_protocol_unwrap(self):
        from drive_local_open.cli import unwrap_protocol_url
        u = unwrap_protocol_url(
            "drive-local-open://open?url=https%3A%2F%2Fdrive.google.com%2Fdrive%2Ffolders%2Fabc"
        )
        self.assertEqual(u, "https://drive.google.com/drive/folders/abc")



class ResolveFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mydrive = self.root / "マイドライブ"
        self.mydrive.mkdir()
        self.bank = self.mydrive / "Bank"
        self.bank.mkdir()
        self.db = self.root / "metadata_sqlite_db"
        con = sqlite3.connect(self.db)
        con.executescript(
            """
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
            INSERT INTO items(stable_id,id,is_folder,local_title) VALUES
              (1,'rootMyDrive',1,'マイドライブ'),
              (2,'idBank',1,'Bank'),
              (3,'deadItem',1,'Gone');
            UPDATE items SET is_tombstone=1 WHERE id='deadItem';
            INSERT INTO stable_parents(item_stable_id,parent_stable_id) VALUES (2,1);
            """
        )
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_my_drive(self):
        self.assertEqual(my_drive_path(self.root), self.mydrive)

    def test_metadata_resolve(self):
        result = resolve_via_metadata([self.root], "idBank", db_path=self.db)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.path.resolve(), self.bank.resolve())
        self.assertEqual(result.source, "metadata")

    def test_tombstone(self):
        with self.assertRaises(DriveLocalOpenError) as ctx:
            resolve_via_metadata([self.root], "deadItem", db_path=self.db)
        self.assertEqual(ctx.exception.code, "S8")

    def test_shortcut_fallback(self):
        sid = "sharedABC"
        sc = self.root / ".shortcut-targets-by-id" / sid
        sc.mkdir(parents=True)
        con = sqlite3.connect(self.db)
        con.execute(
            "INSERT INTO items(stable_id,id,is_folder,local_title) VALUES (9,? ,1,?)",
            (sid, "SharedFolder"),
        )
        con.commit()
        con.close()
        result = resolve_via_metadata([self.root], sid, db_path=self.db)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "shortcut")


if __name__ == "__main__":
    unittest.main()
