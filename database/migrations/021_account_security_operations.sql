ALTER TABLE users ADD COLUMN phone_verified_at TEXT;
ALTER TABLE users ADD COLUMN email_verified_at TEXT;
ALTER TABLE users ADD COLUMN password_changed_at TEXT;
ALTER TABLE users ADD COLUMN last_login_at TEXT;

ALTER TABLE web_sessions ADD COLUMN id TEXT;
ALTER TABLE web_sessions ADD COLUMN last_seen_at TEXT;
ALTER TABLE web_sessions ADD COLUMN user_agent TEXT;
ALTER TABLE web_sessions ADD COLUMN ip_address TEXT;
UPDATE web_sessions
SET id = 'session-' || lower(hex(randomblob(12))),
    last_seen_at = COALESCE(last_seen_at, created_at)
WHERE id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_web_sessions_id ON web_sessions(id);

CREATE TABLE IF NOT EXISTS login_audit_events (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  identifier TEXT NOT NULL,
  success INTEGER NOT NULL CHECK (success IN (0, 1)),
  reason TEXT,
  ip_address TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_login_audit_user ON login_audit_events(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS platform_announcements (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  audience TEXT NOT NULL DEFAULT 'all' CHECK (audience IN ('all', 'buyer', 'seller')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  published_at TEXT,
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_platform_announcements_public
  ON platform_announcements(status, published_at DESC);

CREATE TABLE IF NOT EXISTS platform_campaigns (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  campaign_type TEXT NOT NULL CHECK (campaign_type IN ('coupon', 'full_reduction')),
  rule_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'ended')),
  starts_at TEXT,
  ends_at TEXT,
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
