CREATE TABLE IF NOT EXISTS shop_messages (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  sender_role TEXT NOT NULL CHECK (sender_role IN ('buyer', 'seller')),
  content TEXT NOT NULL,
  read_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shop_messages_conversation
  ON shop_messages(shop_id, buyer_user_id, created_at);
