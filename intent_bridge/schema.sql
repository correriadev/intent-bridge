PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;

CREATE TABLE session (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'closed')),
    request TEXT NOT NULL,
    facilitator TEXT NOT NULL,
    participant TEXT NOT NULL,
    current_version TEXT
);

CREATE TABLE version (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES session(id),
    revision INTEGER NOT NULL,
    parent_id TEXT REFERENCES version(id),
    author TEXT NOT NULL,
    content BLOB NOT NULL,
    sha256 TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, revision)
);

CREATE TABLE event (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL REFERENCES session(id),
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    facilitator TEXT NOT NULL,
    version_id TEXT REFERENCES version(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE contribution (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event(id),
    version_id TEXT NOT NULL REFERENCES version(id),
    presentation_id TEXT NOT NULL REFERENCES event(id),
    text TEXT NOT NULL
);

CREATE TABLE version_contribution (
    version_id TEXT NOT NULL REFERENCES version(id),
    contribution_id TEXT NOT NULL REFERENCES contribution(id),
    PRIMARY KEY(version_id, contribution_id)
);

CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES version(id),
    presentation_id TEXT NOT NULL REFERENCES event(id),
    contribution_id TEXT NOT NULL REFERENCES contribution(id),
    location TEXT NOT NULL,
    observation TEXT NOT NULL
);

CREATE TABLE checkpoint (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES version(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    kind TEXT NOT NULL CHECK (kind IN ('change', 'learning')),
    description TEXT NOT NULL,
    predecessor_id TEXT REFERENCES checkpoint(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'integrated', 'reopened'))
);

CREATE TABLE attempt (
    id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL REFERENCES checkpoint(id),
    version_id TEXT NOT NULL REFERENCES version(id),
    presentation_id TEXT NOT NULL REFERENCES event(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'captured', 'cancelled', 'invalidated'))
);

CREATE TABLE checkpoint_event (
    checkpoint_id TEXT NOT NULL REFERENCES checkpoint(id),
    event_id TEXT NOT NULL REFERENCES event(id),
    PRIMARY KEY (checkpoint_id, event_id)
);

CREATE TABLE human_capture (
    event_id TEXT PRIMARY KEY REFERENCES event(id),
    attempt_id TEXT UNIQUE NOT NULL REFERENCES attempt(id)
);

CREATE TABLE recognition (
    id TEXT PRIMARY KEY,
    checkpoint_id TEXT NOT NULL REFERENCES checkpoint(id),
    event_id TEXT UNIQUE NOT NULL REFERENCES event(id),
    receipt TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(checkpoint_id)
);
