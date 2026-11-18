"""Persistent conversation graph. Tool inputs represent agent declarations."""

import json

from .session import Session, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_session (
    id TEXT PRIMARY KEY, objective TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_turn (
    session_id TEXT NOT NULL REFERENCES graph_session(id),
    id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
    created_at TEXT NOT NULL, PRIMARY KEY(session_id,id)
);
CREATE TABLE IF NOT EXISTS graph_record (
    seq INTEGER PRIMARY KEY, session_id TEXT NOT NULL, turn_id TEXT NOT NULL,
    kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
    source TEXT, target TEXT, type TEXT NOT NULL,
    FOREIGN KEY(session_id,turn_id) REFERENCES graph_turn(session_id,id),
    UNIQUE(session_id,kind,id)
);
"""


class Graph:
    def __init__(self, db):
        self.db = db
        self.transaction = Session(db).transaction
        db.executescript(SCHEMA)

    def open_session(self, session_id, objective):
        with self.transaction():
            self.db.execute("INSERT INTO graph_session VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
                            (session_id, objective, now()))
            stored = self.db.execute("SELECT objective FROM graph_session WHERE id=?", (session_id,)).fetchone()
            if stored[0] != objective:
                raise ValueError("A sessão já existe com outro objetivo")
        return {"session_id": session_id}

    def record_turn(self, session_id, turn_id, role, text):
        values = (session_id, turn_id, role, text)
        with self.transaction():
            self.db.execute("INSERT INTO graph_turn VALUES (?,?,?,?,?) ON CONFLICT(session_id,id) DO NOTHING",
                            (*values, now()))
            row = self.db.execute("SELECT role,text FROM graph_turn WHERE session_id=? AND id=?",
                                  values[:2]).fetchone()
            if tuple(row) != values[2:]:
                raise ValueError("O identificador do turno já tem outro conteúdo")
        return {"turn_id": turn_id, "origin": "codex_declared"}

    def write_graph(self, session_id, turn_id, nodes, edges):
        with self.transaction():
            if not self.db.execute("SELECT 1 FROM graph_turn WHERE session_id=? AND id=?",
                                   (session_id, turn_id)).fetchone():
                raise ValueError("Turno não encontrado nesta sessão")
            for kind, items in (("node", nodes), ("edge", edges)):
                for item in items:
                    source, target = item.get("source"), item.get("target")
                    if kind == "edge":
                        for endpoint in (source, target):
                            if not self.db.execute(
                                "SELECT 1 FROM graph_record WHERE session_id=? AND kind='node' AND id=?",
                                (session_id, endpoint)
                            ).fetchone():
                                raise ValueError("A aresta requer dois nós da mesma sessão")
                    data = json.dumps(item, sort_keys=True, ensure_ascii=False, allow_nan=False)
                    self.db.execute(
                        "INSERT INTO graph_record(session_id,turn_id,kind,id,data,source,target,type) "
                        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(session_id,kind,id) DO NOTHING",
                        (session_id, turn_id, kind, item["id"], data, source, target, item["type"]))
                    row = self.db.execute(
                        "SELECT turn_id,data FROM graph_record WHERE session_id=? AND kind=? AND id=?",
                        (session_id, kind, item["id"])).fetchone()
                    if tuple(row) != (turn_id, data):
                        raise ValueError("O identificador já tem outro conteúdo ou origem")
        return {"nodes": [node["id"] for node in nodes], "edges": [edge["id"] for edge in edges]}

    def list_sessions(self, limit=50):
        return {"sessions": [dict(row) for row in self.db.execute(
            "SELECT * FROM graph_session ORDER BY created_at DESC,id LIMIT ?", (limit,))]}

    def query_graph(self, session_id, kind=None, type=None, node_id=None, limit=50, after=0):
        rows = self.db.execute(
            "SELECT seq,kind,turn_id,data FROM graph_record WHERE session_id=? AND seq>? "
            "AND (? IS NULL OR kind=?) AND (? IS NULL OR type=?) "
            "AND (? IS NULL OR source=? OR target=? OR (kind='node' AND id=?)) ORDER BY seq LIMIT ?",
            (session_id, after, kind, kind, type, type, node_id, node_id, node_id, node_id, limit + 1)
        ).fetchall()
        return {
            "records": [{"kind": row["kind"], "turn_id": row["turn_id"], **json.loads(row["data"])}
                        for row in rows[:limit]],
            "next_after": rows[limit - 1]["seq"] if len(rows) > limit else None,
        }

    def get_node(self, session_id, node_id):
        row = self.db.execute(
            "SELECT r.data,t.id,t.role,t.text FROM graph_record r JOIN graph_turn t "
            "ON t.session_id=r.session_id AND t.id=r.turn_id "
            "WHERE r.session_id=? AND r.kind='node' AND r.id=?", (session_id, node_id)).fetchone()
        if row is None:
            raise ValueError("Nó não encontrado")
        return {
            "node": json.loads(row["data"]),
            "turn": {"id": row["id"], "role": row["role"], "text": row["text"], "origin": "codex_declared"},
            "relations": self.query_graph(session_id, kind="edge", node_id=node_id),
        }
