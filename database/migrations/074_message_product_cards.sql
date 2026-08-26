ALTER TABLE shop_messages ADD COLUMN product_id TEXT REFERENCES products(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_shop_messages_product
  ON shop_messages(product_id, created_at DESC);
