CREATE TABLE IF NOT EXISTS activity_order_allocations (
  id TEXT PRIMARY KEY,
  activity_product_id TEXT NOT NULL REFERENCES activity_products(id) ON DELETE RESTRICT,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  order_item_id TEXT NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE CASCADE,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved', 'redeemed', 'released', 'reversed')),
  redeemed_at TEXT,
  released_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(activity_product_id, order_item_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_order_allocations_order
  ON activity_order_allocations(order_id, status);
CREATE INDEX IF NOT EXISTS idx_activity_order_allocations_product
  ON activity_order_allocations(activity_product_id, status);
