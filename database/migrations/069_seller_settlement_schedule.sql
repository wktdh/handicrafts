-- Platform-side settlement timing. Actual payouts remain provider-integrated work.
ALTER TABLE seller_profiles ADD COLUMN payout_schedule TEXT NOT NULL DEFAULT 'weekly'
  CHECK (payout_schedule IN ('daily', 'weekly', 'biweekly', 'monthly'));
ALTER TABLE seller_profiles ADD COLUMN payout_schedule_updated_at TEXT;
-- Reserved for the 90-day new-seller risk policy. It remains zero until the
-- platform publishes the additional number of business days.
ALTER TABLE seller_profiles ADD COLUMN payout_risk_hold_business_days INTEGER NOT NULL DEFAULT 0
  CHECK (payout_risk_hold_business_days BETWEEN 0 AND 90);

ALTER TABLE shop_settlements ADD COLUMN hold_started_at TEXT;
ALTER TABLE shop_settlements ADD COLUMN hold_until TEXT;
CREATE INDEX IF NOT EXISTS idx_shop_settlements_hold_release
  ON shop_settlements(status, hold_until);
