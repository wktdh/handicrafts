CREATE TABLE IF NOT EXISTS governance_appeals (
  id TEXT PRIMARY KEY,
  appellant_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'shop', 'user')),
  target_id TEXT NOT NULL,
  content TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  handled_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  resolution_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  handled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_governance_appeals_queue
  ON governance_appeals(status, created_at DESC);

CREATE TABLE IF NOT EXISTS enforcement_actions (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'shop', 'user')),
  target_id TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('warning', 'unlist_product', 'pause_shop', 'disable_user')),
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  revoked_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS governance_notifications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  related_type TEXT,
  related_id TEXT,
  read_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_notifications_user
  ON governance_notifications(user_id, read_at, created_at DESC);
