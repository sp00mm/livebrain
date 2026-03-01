-- Livebrain database schema

CREATE TABLE IF NOT EXISTS brains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    default_model_config_json TEXT DEFAULT '{}',
    template_type TEXT,
    system_prompt TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brain_tools (
    id TEXT PRIMARY KEY,
    brain_id TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    config_json TEXT,
    enabled INTEGER DEFAULT 1,
    position INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_brain_tools_brain ON brain_tools(brain_id);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    brain_id TEXT NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    model_config_override_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_questions_brain ON questions(brain_id);

CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER,
    file_count INTEGER,
    index_status TEXT NOT NULL DEFAULT 'pending',
    indexed_at TEXT,
    index_error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brain_resources (
    brain_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (brain_id, resource_id),
    FOREIGN KEY (brain_id) REFERENCES brains(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_brain_resources_brain ON brain_resources(brain_id);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    filepath TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding f32_blob(768),
    source_meta TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_resource ON document_chunks(resource_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks(libsql_vector_idx(embedding));

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    audio_input_device TEXT,
    audio_output_device TEXT,
    is_live INTEGER NOT NULL DEFAULT 0,
    current_brain_id TEXT,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY (current_brain_id) REFERENCES brains(id)
);

CREATE TABLE IF NOT EXISTS transcript_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    speaker TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_transcript_session ON transcript_entries(session_id, timestamp);

CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    brain_id TEXT NOT NULL,
    question_id TEXT,
    query_type TEXT NOT NULL,
    query_text TEXT NOT NULL,
    transcript_snapshot_json TEXT,
    artifacts_used_json TEXT,
    system_prompt TEXT,
    tools_json TEXT,
    messages_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (brain_id) REFERENCES brains(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_interaction ON tool_calls(interaction_id);

CREATE TABLE IF NOT EXISTS ai_responses (
    id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL,
    file_references_json TEXT,
    model_used TEXT NOT NULL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS execution_steps (
    id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_steps_interaction ON execution_steps(interaction_id);

CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    default_input_device TEXT,
    default_output_device TEXT,
    default_brain_id TEXT,
    preferred_model TEXT DEFAULT '',
    data_directory TEXT,
    max_session_storage_days INTEGER DEFAULT 30,
    onboarding_complete INTEGER DEFAULT 0,
    FOREIGN KEY (default_brain_id) REFERENCES brains(id)
);
INSERT OR IGNORE INTO user_settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS chat_feed_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL,
    thread_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_feed_items_session ON chat_feed_items(session_id, position);
