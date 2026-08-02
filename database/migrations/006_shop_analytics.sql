CREATE TABLE IF NOT EXISTS shop_analytics (
  shop_id TEXT PRIMARY KEY REFERENCES shops(id) ON DELETE CASCADE,
  visitor_count INTEGER NOT NULL DEFAULT 0 CHECK (visitor_count >= 0),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shop_visit_events (
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  visitor_key TEXT NOT NULL,
  visited_on TEXT NOT NULL DEFAULT CURRENT_DATE,
  PRIMARY KEY (shop_id, visitor_key, visited_on)
);

CREATE INDEX IF NOT EXISTS idx_shop_visit_events_shop_date ON shop_visit_events(shop_id, visited_on DESC);
