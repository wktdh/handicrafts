ALTER TABLE activity_products ADD COLUMN reviewer_user_id TEXT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE activity_products ADD COLUMN review_note TEXT;
ALTER TABLE activity_products ADD COLUMN reviewed_at TEXT;
ALTER TABLE activity_products ADD COLUMN updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_activity_products_review_queue
  ON activity_products(activity_id, status, created_at DESC);
