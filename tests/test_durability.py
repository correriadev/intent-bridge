import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from intent_bridge.session import Session
from intent_bridge.store import connect, initialize, verify


class DurabilityTest(unittest.TestCase):
    def database_path(self):
        descriptor, name = tempfile.mkstemp(suffix=".sqlite3", dir=Path.cwd())
        os.close(descriptor)
        self.addCleanup(lambda: Path(name).unlink(missing_ok=True))
        return Path(name)

    def test_retry_concurrently_and_restore_backup(self):
        path = self.database_path()
        backup = self.database_path()
        db = connect(path)
        initialize(db)
        service = Session(db)
        service.create("pedido", "facilitador", "participante", "dados fictícios")
        version = service.current()
        presentation = service.record_presentation(version["id"], version["sha256"])
        feedback = service.feedback(presentation, "Rejeito este rascunho", "rejection")
        checkpoint = service.propose(presentation, feedback, "linha 1", "Rascunho rejeitado",
                                     "learning", "A necessidade não está clara")
        attempt = service.begin_attempt(checkpoint, presentation)
        event = service.capture(attempt, "Entendi que ainda preciso definir minha necessidade")
        db.close()

        def confirm():
            connection = connect(path)
            try:
                return Session(connection).confirm(checkpoint, event)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: confirm(), range(2)))
        self.assertEqual(receipts[0], receipts[1])
        db = connect(path)
        restored = connect(backup)
        try:
            db.backup(restored)
            verify(restored)
            self.assertEqual(1, restored.execute("SELECT count(*) FROM recognition").fetchone()[0])
            self.assertEqual(receipts[0], Session(restored).confirm(checkpoint, event))
        finally:
            restored.close()
            db.close()

    def test_interrupted_transaction_rolls_back_on_reopen(self):
        path = self.database_path()
        db = connect(path)
        initialize(db)
        Session(db).create("pedido", "facilitador", "participante", "dados fictícios")
        db.close()
        script = (
            "import sqlite3,sys; "
            "db=sqlite3.connect(sys.argv[1], autocommit=True); "
            "db.execute('BEGIN IMMEDIATE'); "
            "db.execute(\"UPDATE session SET status='closed'\"); "
            "print('ready', flush=True); sys.stdin.readline()"
        )
        child = subprocess.Popen([sys.executable, "-c", script, str(path)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual("ready", child.stdout.readline().strip())
        finally:
            child.kill()
            child.communicate(timeout=10)
        db = connect(path)
        try:
            verify(db)
            self.assertEqual("active", Session(db).session()["status"])
        finally:
            db.close()
