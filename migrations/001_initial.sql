-- 001_initial.sql

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    auth_provider TEXT NOT NULL DEFAULT 'workos',
    auth_subject TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst', 'manager', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS user_jurisdictions (
    user_id TEXT NOT NULL REFERENCES users(id),
    jurisdiction TEXT NOT NULL CHECK (jurisdiction IN ('US', 'EU')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, jurisdiction)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS regulations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    jurisdiction TEXT NOT NULL CHECK (jurisdiction IN ('US', 'EU')),
    regulator TEXT NOT NULL CHECK (regulator IN ('SEC', 'CFTC', 'EUR_LEX')),
    document_type TEXT NOT NULL,
    publication_date TEXT,
    effective_date TEXT,
    enforcement_date TEXT,
    source_url TEXT,
    license_note TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    version TEXT NOT NULL DEFAULT '1.0',
    parent_regulation_id TEXT REFERENCES regulations(id),
    document_hash TEXT UNIQUE,
    original_filename TEXT,
    mime_type TEXT,
    file_size_bytes INTEGER,
    original_file_path TEXT,
    extracted_text_path TEXT,
    normalized_json_path TEXT,
    index_status TEXT NOT NULL DEFAULT 'ingesting' CHECK (index_status IN ('ingesting', 'indexed', 'failed', 'stale')),
    full_text TEXT,
    summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS regulation_chunks (
    id TEXT PRIMARY KEY,
    regulation_id TEXT NOT NULL REFERENCES regulations(id),
    document_hash TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    section_id TEXT NOT NULL,
    section_path TEXT,
    heading TEXT,
    text TEXT NOT NULL,
    token_count INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    block_type TEXT DEFAULT 'paragraph',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_regulation_id ON regulation_chunks(regulation_id);
CREATE INDEX IF NOT EXISTS idx_chunks_section_id ON regulation_chunks(section_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    section_path,
    heading,
    content='regulation_chunks',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS regulation_relationships (
    id TEXT PRIMARY KEY,
    source_regulation_id TEXT NOT NULL REFERENCES regulations(id),
    related_regulation_id TEXT NOT NULL REFERENCES regulations(id),
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('AMENDS', 'REFERENCES', 'SUPERSEDES', 'CLARIFIES', 'RELATED_TOPIC')),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    admin_user_id TEXT NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'indexed', 'failed')),
    current_step TEXT,
    error_message TEXT,
    regulation_id TEXT REFERENCES regulations(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    primary_regulation_id TEXT NOT NULL REFERENCES regulations(id),
    title TEXT NOT NULL,
    summary TEXT,
    applicability TEXT,
    key_obligations TEXT,
    affected_business_lines TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(affected_business_lines)),
    affected_systems TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(affected_systems)),
    effective_date TEXT,
    deadline_date TEXT,
    risk_rating TEXT CHECK (risk_rating IN ('low', 'medium', 'high', 'critical')),
    implementation_effort TEXT CHECK (implementation_effort IN ('low', 'medium', 'high')),
    status TEXT NOT NULL CHECK (status IN ('draft', 'submitted', 'revisions_requested', 'approved')),
    created_by_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT,
    approved_at TEXT,
    approved_by_user_id TEXT REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_assessments_primary_regulation_id ON assessments(primary_regulation_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_created_by_user_id ON assessments(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_assessments_approved_by_user_id ON assessments(approved_by_user_id);

CREATE TABLE IF NOT EXISTS assessment_regulations (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    regulation_id TEXT NOT NULL REFERENCES regulations(id),
    relationship_type TEXT NOT NULL DEFAULT 'context',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(assessment_id, regulation_id)
);

CREATE INDEX IF NOT EXISTS idx_assessment_regulations_assessment_id ON assessment_regulations(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_regulations_regulation_id ON assessment_regulations(regulation_id);

CREATE TABLE IF NOT EXISTS assessment_versions (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    version_number INTEGER NOT NULL,
    status_at_creation TEXT NOT NULL,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    created_by_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assessment_citations (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    chunk_id TEXT NOT NULL REFERENCES regulation_chunks(id),
    quote TEXT NOT NULL,
    citation_text TEXT NOT NULL,
    field_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assessment_reviews (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id),
    actor_user_id TEXT NOT NULL REFERENCES users(id),
    action TEXT NOT NULL CHECK (action IN ('revisions_requested', 'approved')),
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qa_interactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    assessment_id TEXT REFERENCES assessments(id),
    query TEXT NOT NULL,
    answer TEXT,
    model TEXT,
    provider TEXT,
    retrieved_chunk_ids TEXT CHECK (json_valid(retrieved_chunk_ids)),
    citations_json TEXT CHECK (json_valid(citations_json)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata)),
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_actor_created ON audit_logs(actor_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity_created ON audit_logs(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action_created ON audit_logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
