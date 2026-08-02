CREATE TABLE IF NOT EXISTS platform_campaign_claims (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE RESTRICT,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  claimed_quantity INTEGER NOT NULL DEFAULT 1 CHECK (claimed_quantity > 0),
  used_quantity INTEGER NOT NULL DEFAULT 0 CHECK (used_quantity >= 0 AND used_quantity <= claimed_quantity),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(campaign_id, buyer_user_id)
);
CREATE INDEX IF NOT EXISTS idx_campaign_claims_buyer ON platform_campaign_claims(buyer_user_id, updated_at DESC);

ALTER TABLE platform_campaigns ADD COLUMN per_user_claim_limit INTEGER NOT NULL DEFAULT 1 CHECK (per_user_claim_limit > 0);
ALTER TABLE platform_campaign_redemptions ADD COLUMN claim_id TEXT REFERENCES platform_campaign_claims(id) ON DELETE RESTRICT;
