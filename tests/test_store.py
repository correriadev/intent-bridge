import hashlib
import unittest

from intent_bridge.store import connect, initialize, verify


class StoreTest(unittest.TestCase):
    def test_integrity_detects_changed_snapshot(self):
        with self.subTest("snapshot"):
            db = connect(":memory:")
            self.addCleanup(db.close)
            initialize(db)
            db.execute(
                "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("s", "2026-01-01", "active", "pedido", "f", "p", "v"),
            )
            content = b"draft"
            db.execute(
                "INSERT INTO version VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("v", "s", 1, None, "f", content,
                 hashlib.sha256(content).hexdigest(), "", "2026-01-01"),
            )
            verify(db)
            db.execute("UPDATE version SET content = ?", (b"changed",))
            with self.assertRaises(ValueError):
                verify(db)
