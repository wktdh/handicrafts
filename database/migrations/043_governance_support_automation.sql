CREATE TABLE IF NOT EXISTS service_automation_rules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  keywords_json TEXT NOT NULL DEFAULT '[]',
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  route TEXT NOT NULL DEFAULT 'shop' CHECK (route IN ('shop', 'platform')),
  reply_template TEXT,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 100,
  created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_service_automation_rules_queue ON service_automation_rules(enabled, sort_order, updated_at DESC);

CREATE TABLE IF NOT EXISTS support_ticket_events (
  id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_support_ticket_events_ticket ON support_ticket_events(ticket_id, created_at);

ALTER TABLE support_tickets ADD COLUMN first_response_due_at TEXT;
ALTER TABLE support_tickets ADD COLUMN resolution_due_at TEXT;
ALTER TABLE support_tickets ADD COLUMN automation_rule_id TEXT REFERENCES service_automation_rules(id) ON DELETE SET NULL;
ALTER TABLE support_tickets ADD COLUMN auto_assigned_at TEXT;
ALTER TABLE support_tickets ADD COLUMN escalated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_support_tickets_automation_sla
  ON support_tickets(status, first_response_due_at, resolution_due_at, escalated_at);
