-- RelationInsight v0.1 schema (sync sqlite3)
-- Core: conversations, persons, messages, analyses, evidence, profile_versions
-- Privacy: consents (UI checkbox)

PRAGMA foreign_keys = ON;

-- 会话主表（ARCHITECTURE.md 4.2，2026-09-22 拍板创建；T-007 级联删除的根）
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('A', 'B')),
    display_label TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    sent_at TEXT,
    body TEXT NOT NULL,
    source_line INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (person_id) REFERENCES persons (id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    message_id_from TEXT,
    message_id_to TEXT,
    seq_from INTEGER NOT NULL,
    seq_to INTEGER NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    claim_key TEXT NOT NULL,
    message_id TEXT NOT NULL,
    quote TEXT NOT NULL,
    speaker_role TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses (id),
    FOREIGN KEY (message_id) REFERENCES messages (message_id)
);

CREATE TABLE IF NOT EXISTS profile_versions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changelog_json TEXT,
    message_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (conversation_id, version)
);

CREATE TABLE IF NOT EXISTS consents (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    granted INTEGER NOT NULL CHECK (granted IN (0, 1)),
    scope TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations (status);
CREATE INDEX IF NOT EXISTS idx_persons_conversation ON persons (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_person ON messages (person_id);
CREATE INDEX IF NOT EXISTS idx_analyses_conversation ON analyses (conversation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_conversation ON evidence (conversation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_message ON evidence (message_id);
CREATE INDEX IF NOT EXISTS idx_profile_versions_conversation ON profile_versions (conversation_id);
CREATE INDEX IF NOT EXISTS idx_consents_conversation ON consents (conversation_id);
