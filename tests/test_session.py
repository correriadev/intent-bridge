import unittest

from intent_bridge.session import Session
from intent_bridge.store import connect, initialize


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.s = Session(self.db)
        self.s.create("pedido", "facilitador", "pessoa", "Rascunho fictício")
        version = self.s.current()
        self.presentation = self.s.record_presentation(version["id"], version["sha256"])
        self.feedback = self.s.feedback(self.presentation, "Gostaria de outra organização")

    def candidate(self):
        return self.s.propose(self.presentation, self.feedback, "linha 1", "Conteúdo visível",
                              "learning", "A organização precisa ser revista")

    def test_recognition_is_idempotent_and_reopening_preserves_receipt(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        event = self.s.capture(attempt, "Entendi que preciso de outra organização")
        receipt = self.s.confirm(candidate, event)
        self.assertEqual(receipt, self.s.confirm(candidate, event))
        self.s.reopen(candidate, "Quero reconsiderar")
        self.assertEqual(receipt, self.s.confirm(candidate, event))
        self.assertEqual(1, self.db.execute("SELECT count(*) FROM recognition").fetchone()[0])
        successor = self.s.propose(self.presentation, self.feedback, "linha 1", "Novo entendimento",
                                   "learning", "Revisão do aprendizado", candidate)
        self.assertEqual(candidate, self.db.execute(
            "SELECT predecessor_id FROM checkpoint WHERE id=?", (successor,)).fetchone()[0])
        self.assertEqual("pending", self.db.execute(
            "SELECT status FROM checkpoint WHERE id=?", (successor,)).fetchone()[0])
        self.assertEqual(1, self.db.execute(
            "SELECT count(*) FROM checkpoint_event ce JOIN event e ON e.id=ce.event_id "
            "WHERE ce.checkpoint_id=? AND e.kind='reopen'", (candidate,)).fetchone()[0])

    def test_stale_and_invalidated_attempts_cannot_integrate(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        event = self.s.capture(attempt, "Aprendi algo")
        self.s.revise("Rascunho revisado", "Mudou organização", self.feedback)
        with self.assertRaises(ValueError):
            self.s.confirm(candidate, event)
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM recognition").fetchone()[0])

    def test_nonhuman_event_cannot_integrate(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        with self.s.transaction():
            event = self.s.event("proposal", "model", "human", self.s.current()["id"])
        with self.assertRaises(ValueError):
            self.s.confirm(candidate, event)
        self.s.cancel_attempt(attempt, "cancelado")
        with self.assertRaises(ValueError):
            self.s.capture(attempt, "fala")

    def test_rejected_draft_learning_and_resume(self):
        rejected = self.s.feedback(self.presentation, "Não atende ao que preciso", "rejection")
        candidate = self.s.propose(self.presentation, rejected, "linha 1", "Primeiro rascunho",
                                   "learning", "A necessidade ainda não está clara")
        attempt = self.s.begin_attempt(candidate, self.presentation)
        event = self.s.capture(attempt, "Aprendi que minha necessidade ainda não está clara")
        self.s.change_status("paused")
        self.s.resume()
        with self.assertRaises(ValueError):
            self.s.confirm(candidate, event)
        self.assertEqual("pending", self.db.execute(
            "SELECT status FROM checkpoint WHERE id=?", (candidate,)).fetchone()[0])
        self.assertEqual("rejection", self.db.execute(
            "SELECT kind FROM event WHERE id=(SELECT event_id FROM contribution WHERE id=?)",
            (rejected,)).fetchone()[0])
        with self.assertRaises(ValueError):
            self.s.begin_attempt(candidate, self.presentation)
        version = self.s.current()
        new_presentation = self.s.record_presentation(version["id"], version["sha256"])
        attempt = self.s.begin_attempt(candidate, new_presentation)
        event = self.s.capture(attempt, "Agora sei que preciso esclarecer minha necessidade")
        self.assertTrue(self.s.confirm(candidate, event))

    def test_inconsistent_evidence_is_rejected(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        event = self.s.capture(attempt, "A organização precisa ser revista")
        with self.s.transaction():
            self.db.execute("UPDATE event SET text='wrong digest' WHERE id=?", (self.presentation,))
        with self.assertRaises(ValueError):
            self.s.confirm(candidate, event)
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM recognition").fetchone()[0])

    def test_close_without_checkpoint_and_no_resume(self):
        self.s.change_status("closed")
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM checkpoint").fetchone()[0])
        with self.assertRaises(ValueError):
            self.s.resume()

    def test_revision_keeps_original_and_feedback(self):
        original = self.s.current()
        self.s.revise("Nova tela\nç", "Mudança solicitada", self.feedback)
        revised = self.s.current()
        self.assertEqual(original["id"], revised["parent_id"])
        self.assertEqual("Gostaria de outra organização", self.db.execute(
            "SELECT text FROM contribution WHERE id=?", (self.feedback,)).fetchone()[0])
        self.assertEqual(original["content"], self.db.execute(
            "SELECT content FROM version WHERE id=?", (original["id"],)).fetchone()[0])

    def test_presentation_rejects_version_changed_during_display(self):
        old = self.s.current()
        self.s.revise("Nova versão", "Revisão", self.feedback)
        with self.assertRaises(ValueError):
            self.s.record_presentation(old["id"], old["sha256"])

    def test_generic_recognition_is_not_captured(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        with self.assertRaises(ValueError):
            self.s.capture(attempt, "Gostei!")
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM recognition").fetchone()[0])

    def test_cancelled_and_ambiguous_are_pending(self):
        candidate = self.candidate()
        attempt = self.s.begin_attempt(candidate, self.presentation)
        self.s.cancel_attempt(attempt, "ambíguo")
        self.assertEqual("pending", self.db.execute(
            "SELECT status FROM checkpoint WHERE id=?", (candidate,)).fetchone()[0])
        self.assertEqual(0, self.db.execute("SELECT count(*) FROM recognition").fetchone()[0])
