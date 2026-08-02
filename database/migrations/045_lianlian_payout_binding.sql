ALTER TABLE seller_profiles ADD COLUMN payout_provider TEXT NOT NULL DEFAULT 'lianlian';
ALTER TABLE seller_profiles ADD COLUMN payout_binding_status TEXT NOT NULL DEFAULT 'unbound'
  CHECK (payout_binding_status IN ('unbound', 'pending', 'bound', 'failed'));
ALTER TABLE seller_profiles ADD COLUMN payout_account_id TEXT;
ALTER TABLE seller_profiles ADD COLUMN payout_account_mask TEXT;
ALTER TABLE seller_profiles ADD COLUMN payout_bound_at TEXT;
