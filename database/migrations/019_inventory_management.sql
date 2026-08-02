ALTER TABLE products ADD COLUMN low_stock_threshold INTEGER NOT NULL DEFAULT 3 CHECK (low_stock_threshold >= 0);

CREATE TABLE IF NOT EXISTS inventory_adjustments (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  sku_id TEXT REFERENCES product_skus(id) ON DELETE SET NULL,
  operator_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  adjustment_type TEXT NOT NULL CHECK (adjustment_type IN ('set', 'increase', 'decrease', 'bulk_set')),
  quantity_before INTEGER NOT NULL CHECK (quantity_before >= 0),
  quantity_after INTEGER NOT NULL CHECK (quantity_after >= 0),
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_product
  ON inventory_adjustments(product_id, created_at DESC);
