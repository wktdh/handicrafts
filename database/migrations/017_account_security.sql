CREATE TABLE IF NOT EXISTS verification_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  destination TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN ('contact_verify', 'password_reset', 'admin_step_up')),
  token_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verification_tokens_lookup
  ON verification_tokens(destination, purpose, expires_at DESC);
