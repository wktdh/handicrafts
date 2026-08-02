ALTER TABLE shops ADD COLUMN shipping_template_json TEXT NOT NULL DEFAULT '{"name":"标准快递","firstFee":0,"additionalFee":0}';
ALTER TABLE shops ADD COLUMN coupons_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE orders ADD COLUMN discount_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (discount_amount_cents >= 0);

CREATE INDEX IF NOT EXISTS idx_buyer_addresses_default
  ON buyer_addresses(buyer_user_id, is_default DESC, updated_at DESC);
