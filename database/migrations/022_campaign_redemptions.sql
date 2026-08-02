ALTER TABLE platform_campaigns ADD COLUMN budget_cents INTEGER CHECK (budget_cents IS NULL OR budget_cents >= 0);
ALTER TABLE platform_campaigns ADD COLUMN total_usage_limit INTEGER CHECK (total_usage_limit IS NULL OR total_usage_limit > 0);
ALTER TABLE platform_campaigns ADD COLUMN per_user_usage_limit INTEGER NOT NULL DEFAULT 1 CHECK (per_user_usage_limit > 0);

CREATE TABLE IF NOT EXISTS platform_campaign_redemptions (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE RESTRICT,
  order_id TEXT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE RESTRICT,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  item_amount_cents INTEGER NOT NULL CHECK (item_amount_cents >= 0),
  discount_amount_cents INTEGER NOT NULL CHECK (discount_amount_cents > 0),
  status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved', 'redeemed', 'released', 'reversed')),
  redeemed_at TEXT,
  released_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_campaign_redemptions_campaign_status
  ON platform_campaign_redemptions(campaign_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_redemptions_buyer
  ON platform_campaign_redemptions(campaign_id, buyer_user_id, status);
