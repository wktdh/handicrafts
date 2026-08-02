CREATE TABLE IF NOT EXISTS governance_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  keyword TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL CHECK (action IN ('manual_review', 'reject')),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enforcement_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'shop', 'user')),
  action_type TEXT NOT NULL CHECK (action_type IN ('warning', 'unlist_product', 'pause_shop', 'disable_user')),
  reason TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS governance_tasks (
  id TEXT PRIMARY KEY,
  task_type TEXT NOT NULL CHECK (task_type IN ('product_moderation', 'report', 'appeal')),
  target_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
  assigned_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  UNIQUE(task_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_governance_tasks_queue
  ON governance_tasks(status, assigned_user_id, created_at DESC);
