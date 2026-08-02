CREATE INDEX IF NOT EXISTS idx_governance_rule_hits_effectiveness
  ON governance_rule_hits(rule_id, action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_service_sla
  ON support_tickets(status, priority, created_at, assigned_user_id);
