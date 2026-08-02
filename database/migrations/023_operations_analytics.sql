ALTER TABLE orders ADD COLUMN attribution_channel TEXT NOT NULL DEFAULT 'direct';

CREATE TABLE IF NOT EXISTS analytics_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL CHECK (event_type IN ('product_view', 'add_cart', 'checkout_started', 'order_paid')),
  visitor_key TEXT,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  shop_id TEXT REFERENCES shops(id) ON DELETE SET NULL,
  product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
  campaign_id TEXT REFERENCES platform_campaigns(id) ON DELETE SET NULL,
  channel TEXT NOT NULL DEFAULT 'direct',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type_date ON analytics_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_channel_date ON analytics_events(channel, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_events_user_date ON analytics_events(user_id, created_at DESC);
