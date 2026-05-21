SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS recruiters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL UNIQUE,
    source_file TEXT NOT NULL DEFAULT '',
    first_sent_at TEXT,
    last_sent_at TEXT,
    last_email_subject TEXT,
    reply_status INTEGER NOT NULL DEFAULT 0,
    reply_received_at TEXT,
    followup_status TEXT NOT NULL DEFAULT 'none',
    followup_count INTEGER NOT NULL DEFAULT 0,
    last_followup_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER,
    recruiter_email TEXT NOT NULL,
    email_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_html TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    message_id TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_number INTEGER NOT NULL DEFAULT 1,
    subject TEXT,
    body_html TEXT,
    sent_log_id INTEGER,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(recruiter_id, attempt_number),
    FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE,
    FOREIGN KEY(sent_log_id) REFERENCES email_logs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS inbox_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'new',
    interest_status TEXT NOT NULL DEFAULT 'unreviewed',
    notes TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    latest_subject TEXT NOT NULL DEFAULT '',
    latest_preview TEXT NOT NULL DEFAULT '',
    latest_message_id TEXT,
    last_received_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    body_html TEXT NOT NULL DEFAULT '',
    preview_text TEXT NOT NULL DEFAULT '',
    external_message_id TEXT UNIQUE,
    in_reply_to TEXT NOT NULL DEFAULT '',
    references_header TEXT NOT NULL DEFAULT '',
    mailbox TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    sent_at TEXT,
    received_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recruiters_email ON recruiters(email);
CREATE INDEX IF NOT EXISTS idx_recruiters_reply_status ON recruiters(reply_status, followup_status);
CREATE INDEX IF NOT EXISTS idx_email_logs_status_type ON email_logs(status, email_type);
CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at ON email_logs(sent_at);
CREATE INDEX IF NOT EXISTS idx_followups_due_status ON followups(status, due_at);
CREATE INDEX IF NOT EXISTS idx_inbox_replies_status ON inbox_replies(status, archived, last_received_at);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_recruiter ON conversation_messages(recruiter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_received ON conversation_messages(received_at);
"""
