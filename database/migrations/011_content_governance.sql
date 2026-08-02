ALTER TABLE products ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'approved';
ALTER TABLE products ADD COLUMN moderation_reason TEXT;
ALTER TABLE products ADD COLUMN moderated_at TEXT;

CREATE TABLE IF NOT EXISTS product_moderation_logs (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('approved', 'rejected')),
  reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (product_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_product_moderation_logs_product ON product_moderation_logs(product_id, created_at DESC);
