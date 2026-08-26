CREATE TABLE IF NOT EXISTS brand_site_subscribers (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'subscribed' CHECK(status IN ('subscribed', 'unsubscribed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shop_id, email)
);

CREATE INDEX IF NOT EXISTS idx_brand_site_subscribers_shop_status
  ON brand_site_subscribers(shop_id, status, created_at DESC);
