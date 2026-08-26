-- 作品发布分类与店铺经营分类共用。旧表仅允许六个展示分类，
-- 因此需要移除 category 的固定 CHECK 约束，以支持详细经营类目。
PRAGMA foreign_keys = OFF;

CREATE TABLE products_rebuilt (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  material TEXT NOT NULL DEFAULT '',
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'published', 'unlisted', 'archived')),
  published_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  moderation_status TEXT NOT NULL DEFAULT 'approved',
  moderation_reason TEXT,
  moderated_at TEXT,
  low_stock_threshold INTEGER NOT NULL DEFAULT 3 CHECK (low_stock_threshold >= 0),
  supports_custom INTEGER NOT NULL DEFAULT 0 CHECK (supports_custom IN (0, 1))
);

INSERT INTO products_rebuilt (
  id, shop_id, category, title, description, material, price_cents, stock,
  status, published_at, created_at, updated_at, moderation_status,
  moderation_reason, moderated_at, low_stock_threshold, supports_custom
)
SELECT
  id, shop_id, category, title, description, material, price_cents, stock,
  status, published_at, created_at, updated_at, moderation_status,
  moderation_reason, moderated_at, low_stock_threshold, supports_custom
FROM products;

DROP TABLE products;
ALTER TABLE products_rebuilt RENAME TO products;

CREATE INDEX idx_products_discovery ON products(status, category, published_at DESC);
CREATE INDEX idx_products_shop_status ON products(shop_id, status, updated_at DESC);

PRAGMA foreign_keys = ON;
