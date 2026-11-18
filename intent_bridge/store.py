"""SQLite connection and integrity checks."""

import hashlib
import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=5, autocommit=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA synchronous=FULL")
    return db


def initialize(db: sqlite3.Connection) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)


def verify(db: sqlite3.Connection) -> None:
    if db.execute("PRAGMA user_version").fetchone()[0] != 2:
        raise ValueError("Versão de esquema desconhecida")
    if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("Banco de dados corrompido")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Referência inválida no banco")
    for row in db.execute("SELECT content, sha256 FROM version"):
        if hashlib.sha256(row["content"]).hexdigest() != row["sha256"]:
            raise ValueError("Snapshot alterado")
