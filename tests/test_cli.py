import io
import json
import re
from pathlib import Path
import unittest
import uuid
from unittest.mock import Mock, patch

from intent_bridge.cli import main, multiline, present, private_directory, safe
from intent_bridge.session import Session
from intent_bridge.store import connect, initialize


class TerminalTest(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.service = Session(self.db)
        self.service.create("pedido", "facilitador", "pessoa", "Rascunho fictício")

    def test_presentation_requires_facilitator_confirmation(self):
        with patch("builtins.input", return_value="n"), patch("sys.stdout", new_callable=io.StringIO):
            self.assertIsNone(present(self.service))
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM event WHERE kind='presentation'").fetchone()[0])

    def test_multiline_preserves_user_text(self):
        with patch("builtins.input", side_effect=["primeira", "segunda", ".", "s"]), patch(
            "sys.stdout", new_callable=io.StringIO
        ):
            self.assertEqual("primeira\nsegunda", multiline("Texto"))

    def test_terminal_controls_are_escaped(self):
        self.assertEqual("a\\u001b[31m", safe("a\x1b[31m"))

    def test_refusal_creates_no_database(self):
        stdin = Mock()
        stdin.isatty.return_value = True
        with patch("sys.argv", ["intent_bridge", "study"]), patch("sys.stdin", stdin), patch(
            "intent_bridge.cli.data_directory", return_value=Path.cwd()
        ), patch("intent_bridge.cli.connect") as connect_db, patch(
            "builtins.input", side_effect=["pedido", ".", "s", "n"]
        ), patch("sys.stdout", new_callable=io.StringIO):
            main()
        connect_db.assert_not_called()

    @unittest.skipUnless(__import__("os").name == "nt", "Windows ACL")
    def test_acl_rejects_additional_principals(self):
        with patch("intent_bridge.cli.subprocess.run", return_value=Mock(returncode=3)):
            with self.assertRaises(ValueError):
                private_directory(Path.cwd())

    @unittest.skipUnless(__import__("os").name == "nt", "Windows ACL")
    def test_acl_accepts_private_directory(self):
        with patch("intent_bridge.cli.subprocess.run", return_value=Mock(returncode=0)):
            private_directory(Path.cwd())

    def test_terminal_journey_export_and_backup(self):
        stdin = Mock()
        stdin.isatty.return_value = True
        replies = [
            "pedido", ".", "s", "s", "facilitador", "participante",
            "1", "s", "2", "feedback", "Mudar a ordem", ".", "s",
            "3", "1", "Rascunho fictício revisado", ".", "s",
            "Ordem alterada", ".", "s", "s",
            "1", "s", "4", "1", "linha 1", "Ordem nova", ".", "s",
            "change", "A ordem mudou", ".", "s", "n",
            "5", "1", "Agora a ordem ficou clara", ".", "s", "s", "8",
        ]
        output = io.StringIO()
        with patch("sys.argv", ["intent_bridge", "study"]), patch("sys.stdin", stdin), patch(
            "intent_bridge.cli.data_directory", return_value=Path.cwd()
        ), patch("intent_bridge.cli.private_directory"), patch(
            "builtins.input", side_effect=replies
        ), patch("sys.stdout", output):
            main()
        match = re.search(r"Sessão ([0-9a-f-]{36})", output.getvalue())
        self.assertIsNotNone(match)
        session_id = match.group(1)
        database = Path.cwd() / (session_id + ".sqlite3")
        export = Path.cwd() / (str(uuid.uuid4()) + ".json")
        backup = Path.cwd() / (str(uuid.uuid4()) + ".sqlite3")
        for path in (database, export, backup):
            self.addCleanup(lambda path=path: path.unlink(missing_ok=True))
        for command, target in (("export", export), ("backup", backup)):
            with patch("sys.argv", ["intent_bridge", command, "--session", session_id,
                                    "--output", str(target)]), patch(
                "intent_bridge.cli.data_directory", return_value=Path.cwd()
            ), patch("intent_bridge.cli.private_directory"), patch("sys.stdout", new_callable=io.StringIO):
                main()
        records = json.loads(export.read_text(encoding="utf-8"))["records"]
        self.assertEqual(2, len(records["version"]))
        self.assertEqual(1, len(records["recognition"]))
        restored = connect(backup)
        try:
            self.assertEqual(1, restored.execute("SELECT count(*) FROM recognition").fetchone()[0])
        finally:
            restored.close()
