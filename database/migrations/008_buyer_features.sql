CREATE TABLE IF NOT EXISTS buyer_favorites (
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (buyer_user_id, product_id)
);

CREATE TABLE IF NOT EXISTS buyer_shop_follows (
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (buyer_user_id, shop_id)
);

CREATE TABLE IF NOT EXISTS review_images (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS review_followups (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL UNIQUE REFERENCES reviews(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS after_sale_evidence (
  id TEXT PRIMARY KEY,
  after_sale_id TEXT NOT NULL REFERENCES after_sale_requests(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_buyer_favorites ON buyer_favorites(buyer_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_buyer_follows ON buyer_shop_follows(buyer_user_id, created_at DESC);
