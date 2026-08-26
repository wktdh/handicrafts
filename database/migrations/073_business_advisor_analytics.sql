-- SQLite cannot extend a CHECK constraint in place. Rebuild the event table so
-- legacy funnel events and indexes remain available while product-card events
-- gain placement and client supplied idempotency keys.
CREATE TABLE analytics_events_v2 (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL CHECK (event_type IN (
    'product_view', 'add_cart', 'checkout_started', 'order_paid',
    'product_impression', 'product_click', 'favorite_added'
  )),
  visitor_key TEXT,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  shop_id TEXT REFERENCES shops(id) ON DELETE SET NULL,
  product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
  campaign_id TEXT REFERENCES platform_campaigns(id) ON DELETE SET NULL,
  channel TEXT NOT NULL DEFAULT 'direct',
  placement TEXT NOT NULL DEFAULT 'unknown',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO analytics_events_v2 (
  id, event_type, visitor_key, user_id, shop_id, product_id, campaign_id,
  channel, placement, created_at
)
SELECT id, event_type, visitor_key, user_id, shop_id, product_id, campaign_id,
       channel, 'legacy', created_at
FROM analytics_events;

DROP TABLE analytics_events;
ALTER TABLE analytics_events_v2 RENAME TO analytics_events;

-- Recreate every pre-existing analytics index, then add the seller business
-- aggregate indexes used by the data-advisor endpoints.
CREATE INDEX IF NOT EXISTS idx_analytics_events_type_date ON analytics_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_channel_date ON analytics_events(channel, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_user_date ON analytics_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_actor_funnel
  ON analytics_events(user_id, visitor_key, created_at, event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_shop_product_type_date
  ON analytics_events(shop_id, product_id, event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_product_placement_date
  ON analytics_events(product_id, placement, created_at DESC);
