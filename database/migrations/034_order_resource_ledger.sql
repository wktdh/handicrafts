CREATE TABLE IF NOT EXISTS order_inventory_allocations (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  order_item_id TEXT NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE CASCADE,
  product_id TEXT,
  sku_id TEXT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved', 'released', 'reversed')),
  released_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_inventory_allocations_order
  ON order_inventory_allocations(order_id, status);
CREATE INDEX IF NOT EXISTS idx_order_inventory_allocations_sku
  ON order_inventory_allocations(sku_id, status);

INSERT OR IGNORE INTO order_inventory_allocations
  (id, order_id, order_item_id, product_id, sku_id, quantity, status, released_at)
SELECT
  'inventory-allocation-' || order_items.id,
  order_items.order_id,
  order_items.id,
  order_items.product_id,
  order_items.sku_id,
  order_items.quantity,
  CASE
    WHEN orders.status = 'refunded' THEN 'reversed'
    WHEN orders.status = 'cancelled' THEN 'released'
    ELSE 'reserved'
  END,
  CASE WHEN orders.status IN ('cancelled', 'refunded') THEN orders.updated_at ELSE NULL END
FROM order_items
JOIN orders ON orders.id = order_items.order_id;

CREATE TABLE IF NOT EXISTS order_resource_events (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL CHECK (resource_type IN ('sku_inventory', 'campaign_coupon', 'activity_quota')),
  resource_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('reserved', 'redeemed', 'released', 'reversed')),
  quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (amount_cents >= 0),
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_resource_events_order
  ON order_resource_events(order_id, created_at);
CREATE INDEX IF NOT EXISTS idx_order_resource_events_resource
  ON order_resource_events(resource_type, resource_id, created_at);
