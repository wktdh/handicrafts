ALTER TABLE shop_messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text'
  CHECK (message_type IN ('text', 'image', 'order'));
ALTER TABLE shop_messages ADD COLUMN attachment_url TEXT;
ALTER TABLE shop_messages ADD COLUMN order_id TEXT REFERENCES orders(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_shop_messages_unread
  ON shop_messages(shop_id, buyer_user_id, sender_role, read_at, created_at DESC);

CREATE TABLE IF NOT EXISTS seller_quick_replies (
  id TEXT PRIMARY KEY,
  seller_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 500),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(seller_user_id, content)
);

CREATE INDEX IF NOT EXISTS idx_seller_quick_replies_owner
  ON seller_quick_replies(seller_user_id, updated_at DESC);
