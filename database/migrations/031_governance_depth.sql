ALTER TABLE governance_rules ADD COLUMN priority INTEGER NOT NULL DEFAULT 100;
ALTER TABLE governance_rules ADD COLUMN conditions_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE governance_rules ADD COLUMN condition_logic TEXT NOT NULL DEFAULT 'all' CHECK (condition_logic IN ('all', 'any'));
ALTER TABLE governance_rules ADD COLUMN rollout_percent INTEGER NOT NULL DEFAULT 100 CHECK (rollout_percent BETWEEN 0 AND 100);
ALTER TABLE governance_rules ADD COLUMN release_status TEXT NOT NULL DEFAULT 'active' CHECK (release_status IN ('draft', 'active', 'paused'));
ALTER TABLE governance_rules ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS governance_rule_versions (
  id TEXT PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES governance_rules(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(rule_id, version)
);

CREATE TABLE IF NOT EXISTS governance_rule_hits (
  id TEXT PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES governance_rules(id) ON DELETE CASCADE,
  rule_version INTEGER NOT NULL,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  rollout_percent INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_rule_hits_rule ON governance_rule_hits(rule_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_governance_rule_hits_product ON governance_rule_hits(product_id, created_at DESC);

ALTER TABLE governance_tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
  CHECK (priority IN ('low', 'normal', 'high', 'urgent'));
ALTER TABLE governance_tasks ADD COLUMN due_at TEXT;
ALTER TABLE governance_tasks ADD COLUMN last_transferred_at TEXT;

CREATE TABLE IF NOT EXISTS governance_task_transfers (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES governance_tasks(id) ON DELETE CASCADE,
  from_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  to_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  transferred_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS governance_task_notes (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES governance_tasks(id) ON DELETE CASCADE,
  author_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 1000),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS governance_case_events (
  id TEXT PRIMARY KEY,
  case_type TEXT NOT NULL CHECK (case_type IN ('report', 'appeal', 'product')),
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_case_events_case
  ON governance_case_events(case_type, case_id, created_at);

CREATE INDEX IF NOT EXISTS idx_governance_tasks_sla
  ON governance_tasks(status, priority, due_at);
