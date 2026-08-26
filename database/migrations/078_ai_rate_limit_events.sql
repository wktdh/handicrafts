CREATE TABLE ai_rate_limit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scope TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_rate_limit_events_scope_created
  ON ai_rate_limit_events(scope, created_at);
CREATE INDEX idx_ai_rate_limit_events_user_scope_created
  ON ai_rate_limit_events(user_id, scope, created_at);
