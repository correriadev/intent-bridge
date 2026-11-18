"""Transactional operations for a single observed study session."""

import hashlib
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


def identifier():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


def required(value):
    if not value or not value.strip():
        raise ValueError("Campo obrigatório")
    return value


def snapshot(text):
    text = required(text).replace("\r\n", "\n").replace("\r", "\n")
    if any((ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 for c in text):
        raise ValueError("O artefato contém caracteres de controle")
    return text.encode("utf-8")


class Session:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def row(self, sql, params=()):
        row = self.db.execute(sql, params).fetchone()
        if row is None:
            raise ValueError("Registro não encontrado")
        return row

    def session(self):
        return self.row("SELECT * FROM session")

    def active(self):
        session = self.session()
        if session["status"] != "active":
            raise ValueError("Sessão não está ativa")
        return session

    def event(self, kind, actor, text="", version=None):
        session = self.session()
        event_id = identifier()
        self.db.execute(
            "INSERT INTO event(id,session_id,kind,actor,facilitator,version_id,text,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (event_id, session["id"], kind, actor, session["facilitator"], version, text, now()),
        )
        return event_id

    def create(self, request, facilitator, participant, content, session_id=None):
        required(request)
        required(facilitator)
        required(participant)
        data = snapshot(content)
        session_id, version_id = session_id or identifier(), identifier()
        with self.transaction():
            self.db.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?)",
                            (session_id, now(), "active", request, facilitator, participant, version_id))
            self.event("offer_accepted", "participant", "Aceitou experimentar o primeiro rascunho")
            self.db.execute("INSERT INTO version VALUES (?,?,?,?,?,?,?,?,?)",
                            (version_id, session_id, 1, None, facilitator, data,
                             hashlib.sha256(data).hexdigest(), "Primeiro rascunho", now()))
        return session_id

    def current(self):
        return self.row("SELECT * FROM version WHERE id=?", (self.session()["current_version"],))

    def presented(self):
        version = self.current()
        if hashlib.sha256(version["content"]).hexdigest() != version["sha256"]:
            raise ValueError("Snapshot alterado")
        return version

    def record_presentation(self, version_id, digest):
        with self.transaction():
            self.active()
            version = self.presented()
            if version["id"] != version_id or version["sha256"] != digest:
                raise ValueError("Versão alterada durante a apresentação")
            return self.event("presentation", "facilitator", version["sha256"], version["id"])

    def feedback(self, presentation_id, text, kind="feedback"):
        required(text)
        if kind not in ("feedback", "rejection", "reaction"):
            raise ValueError("Tipo de contribuição inválido")
        with self.transaction():
            session = self.active()
            self.row("SELECT id FROM event WHERE id=? AND kind='presentation' AND version_id=?",
                     (presentation_id, session["current_version"]))
            event_id = self.event(kind, "participant", text, session["current_version"])
            contribution_id = identifier()
            self.db.execute("INSERT INTO contribution VALUES (?,?,?,?,?)",
                            (contribution_id, event_id, session["current_version"], presentation_id, text))
            return contribution_id

    def revise(self, content, summary, contribution_id):
        data = snapshot(content)
        required(summary)
        with self.transaction():
            session = self.active()
            previous = self.current()
            self.row("SELECT id FROM contribution WHERE id=? AND version_id=?",
                     (contribution_id, previous["id"]))
            if previous["revision"] >= 2:
                raise ValueError("O roteiro permite uma revisão")
            version_id = identifier()
            self.db.execute("INSERT INTO version VALUES (?,?,?,?,?,?,?,?,?)",
                            (version_id, session["id"], previous["revision"] + 1,
                             previous["id"], session["facilitator"], data,
                             hashlib.sha256(data).hexdigest(), summary, now()))
            self.db.execute("INSERT INTO version_contribution VALUES (?,?)", (version_id, contribution_id))
            self.db.execute("UPDATE session SET current_version=?", (version_id,))
            self.db.execute("UPDATE attempt SET status='invalidated' WHERE status IN ('open','captured')")
            self.event("version_published", "facilitator", summary, version_id)
            return version_id

    def propose(self, presentation_id, contribution_id, location, observation, kind, description, predecessor=None):
        for value in (location, observation, description):
            required(value)
        if kind not in ("change", "learning"):
            raise ValueError("Tipo de checkpoint inválido")
        with self.transaction():
            session = self.active()
            version = self.current()
            self.row("SELECT id FROM event WHERE id=? AND kind='presentation' AND version_id=?",
                     (presentation_id, version["id"]))
            self.row("SELECT c.id FROM contribution c JOIN version v ON c.version_id=v.id "
                     "WHERE c.id=? AND v.session_id=? AND (v.id=? OR v.id=?)",
                     (contribution_id, session["id"], version["id"], version["parent_id"]))
            if predecessor:
                self.row("SELECT id FROM checkpoint WHERE id=? AND status='reopened'", (predecessor,))
            evidence_id, checkpoint_id = identifier(), identifier()
            self.db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                            (evidence_id, version["id"], presentation_id, contribution_id, location, observation))
            self.db.execute("INSERT INTO checkpoint VALUES (?,?,?,?,?,?,?)",
                            (checkpoint_id, version["id"], evidence_id, kind, description, predecessor, "pending"))
            event = self.event("checkpoint_proposed", "facilitator", description, version["id"])
            self.db.execute("INSERT INTO checkpoint_event VALUES (?,?)", (checkpoint_id, event))
            return checkpoint_id

    def begin_attempt(self, checkpoint_id, presentation_id):
        with self.transaction():
            session = self.active()
            candidate = self.row(
                "SELECT c.*,e.presentation_id,v.sha256 FROM checkpoint c "
                "JOIN evidence e ON e.id=c.evidence_id JOIN version v ON v.id=c.version_id "
                "WHERE c.id=? AND c.status='pending' AND c.version_id=?",
                (checkpoint_id, session["current_version"]))
            self.row(
                "SELECT id FROM event WHERE id=? AND kind='presentation' AND session_id=? "
                "AND version_id=? AND text=? AND seq > COALESCE("
                "(SELECT MAX(seq) FROM event WHERE kind IN ('resume','pause')), 0)",
                (presentation_id, session["id"], candidate["version_id"], candidate["sha256"]))
            self.db.execute("UPDATE attempt SET status='invalidated' WHERE status IN ('open','captured')")
            attempt_id = identifier()
            self.db.execute("INSERT INTO attempt VALUES (?,?,?,?,?,?,?)",
                            (attempt_id, checkpoint_id, candidate["version_id"], presentation_id,
                             candidate["evidence_id"], candidate["sha256"], "open"))
            return attempt_id

    def retry_capture(self, checkpoint_id):
        return self.db.execute(
            "SELECT h.event_id FROM human_capture h JOIN attempt a ON a.id=h.attempt_id "
            "WHERE a.checkpoint_id=? AND a.status='captured'", (checkpoint_id,)
        ).fetchone()

    def capture(self, attempt_id, text):
        required(text)
        words = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        if not words or " ".join(words) in {"sim", "ok", "gostei", "bom", "boa", "ótimo", "ótima"}:
            raise ValueError("Reconhecimento ambíguo permanece pendente")
        with self.transaction():
            self.active()
            attempt = self.row("SELECT * FROM attempt WHERE id=? AND status='open'", (attempt_id,))
            event_id = self.event("human_recognition", "participant", text, attempt["version_id"])
            self.db.execute("INSERT INTO human_capture VALUES (?,?)", (event_id, attempt_id))
            self.db.execute("UPDATE attempt SET status='captured' WHERE id=?", (attempt_id,))
            return event_id

    def cancel_attempt(self, attempt_id, reason):
        with self.transaction():
            self.active()
            attempt = self.row("SELECT * FROM attempt WHERE id=? AND status='open'", (attempt_id,))
            self.db.execute("UPDATE attempt SET status='cancelled' WHERE id=?", (attempt_id,))
            self.event("recognition_cancelled", "facilitator", reason, attempt["version_id"])

    def confirm(self, checkpoint_id, event_id):
        with self.transaction():
            prior = self.db.execute("SELECT * FROM recognition WHERE checkpoint_id=?", (checkpoint_id,)).fetchone()
            if prior:
                if prior["event_id"] == event_id:
                    return prior["receipt"]
                raise ValueError("Checkpoint já integrado por outro evento")
            session = self.active()
            self.presented()
            self.row(
                "SELECT a.id FROM attempt a JOIN human_capture h ON h.attempt_id=a.id "
                "JOIN event e ON e.id=h.event_id JOIN checkpoint c ON c.id=a.checkpoint_id "
                "JOIN evidence ev ON ev.id=c.evidence_id JOIN version v ON v.id=c.version_id "
                "JOIN event p ON p.id=ev.presentation_id "
                "JOIN event shown ON shown.id=a.presentation_id "
                "JOIN contribution co ON co.id=ev.contribution_id "
                "JOIN event ce ON ce.id=co.event_id JOIN version cv ON cv.id=co.version_id "
                "WHERE c.id=? AND h.event_id=? AND e.kind='human_recognition' "
                "AND e.actor='participant' AND e.session_id=? AND e.version_id=v.id "
                "AND a.status='captured' AND c.status='pending' AND c.version_id=? "
                "AND a.version_id=v.id AND a.digest=v.sha256 "
                "AND a.evidence_id=ev.id "
                "AND p.kind='presentation' AND p.session_id=e.session_id "
                "AND p.version_id=v.id AND p.text=v.sha256 "
                "AND shown.kind='presentation' AND shown.session_id=e.session_id "
                "AND shown.version_id=v.id AND shown.text=v.sha256 "
                "AND ev.version_id=v.id AND cv.session_id=e.session_id "
                "AND ce.session_id=e.session_id AND ce.version_id=cv.id "
                "AND (cv.id=v.id OR cv.id=v.parent_id)",
                (checkpoint_id, event_id, session["id"], session["current_version"]))
            receipt = identifier()
            self.db.execute("INSERT INTO recognition VALUES (?,?,?,?,?)",
                            (identifier(), checkpoint_id, event_id, receipt, now()))
            self.db.execute("UPDATE checkpoint SET status='integrated' WHERE id=?", (checkpoint_id,))
            return receipt

    def change_status(self, status):
        if status not in ("paused", "closed", "active"):
            raise ValueError("Estado inválido")
        with self.transaction():
            session = self.session()
            if session["status"] == "closed" or (status == "active" and session["status"] != "paused"):
                raise ValueError("Transição inválida")
            self.db.execute("UPDATE attempt SET status='invalidated' WHERE status IN ('open','captured')")
            self.db.execute("UPDATE session SET status=?", (status,))
            self.event({"paused": "pause", "closed": "close", "active": "resume"}[status], "facilitator")

    def resume(self):
        with self.transaction():
            session = self.session()
            if session["status"] == "closed":
                raise ValueError("Sessão encerrada")
            self.db.execute("UPDATE attempt SET status='invalidated' WHERE status IN ('open','captured')")
            self.db.execute("UPDATE session SET status='active'")
            self.event("resume", "facilitator")

    def reopen(self, checkpoint_id, reason):
        required(reason)
        with self.transaction():
            self.active()
            checkpoint = self.row("SELECT * FROM checkpoint WHERE id=? AND status='integrated'", (checkpoint_id,))
            self.db.execute("UPDATE checkpoint SET status='reopened' WHERE id=?", (checkpoint_id,))
            event = self.event("reopen", "participant", reason, checkpoint["version_id"])
            self.db.execute("INSERT INTO checkpoint_event VALUES (?,?)", (checkpoint_id, event))
