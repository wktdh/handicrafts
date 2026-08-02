CREATE TABLE IF NOT EXISTS campaign_coupon_issuances (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE CASCADE,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source TEXT NOT NULL CHECK (source IN ('direct', 'segment', 'code')),
  issued_quantity INTEGER NOT NULL CHECK (issued_quantity > 0),
  created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_campaign_coupon_issuances_campaign
  ON campaign_coupon_issuances(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_coupon_issuances_buyer
  ON campaign_coupon_issuances(buyer_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS campaign_coupon_reminders (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE CASCADE,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reminder_type TEXT NOT NULL CHECK (reminder_type IN ('campaign_expiring', 'code_expiring')),
  code_id TEXT REFERENCES campaign_coupon_codes(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(campaign_id, buyer_user_id, reminder_type)
);
CREATE INDEX IF NOT EXISTS idx_campaign_coupon_reminders_campaign
  ON campaign_coupon_reminders(campaign_id, created_at DESC);
