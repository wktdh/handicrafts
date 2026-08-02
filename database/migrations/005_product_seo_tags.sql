CREATE TABLE IF NOT EXISTS product_seo_tags (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  weight INTEGER NOT NULL DEFAULT 1 CHECK (weight > 0),
  sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
  PRIMARY KEY (product_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_product_seo_tags_tag ON product_seo_tags(tag, weight DESC);
