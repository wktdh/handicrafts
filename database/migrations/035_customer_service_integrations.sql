ALTER TABLE shop_messages ADD COLUMN sender_user_id TEXT REFERENCES users(id) ON DELETE SET NULL;

UPDATE shop_messages
SET sender_user_id = CASE
  WHEN sender_role = 'buyer' THEN buyer_user_id
  ELSE (SELECT owner_user_id FROM shops WHERE shops.id = shop_messages.shop_id)
END
WHERE sender_user_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_shop_messages_sender_user
  ON shop_messages(sender_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS customer_service_conversations (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL CHECK (provider IN ('chaskiq', 'tiledesk', 'papercups')),
  external_conversation_id TEXT NOT NULL,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  channel TEXT NOT NULL DEFAULT 'web',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'archived')),
  last_synced_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, external_conversation_id),
  UNIQUE(provider, shop_id, buyer_user_id, channel)
);

CREATE TABLE IF NOT EXISTS customer_service_message_links (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES customer_service_conversations(id) ON DELETE CASCADE,
  local_message_id TEXT NOT NULL REFERENCES shop_messages(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('chaskiq', 'tiledesk', 'papercups')),
  external_message_id TEXT,
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  sync_status TEXT NOT NULL DEFAULT 'pending' CHECK (sync_status IN ('pending', 'synced', 'failed', 'ignored')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error TEXT,
  synced_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, local_message_id),
  UNIQUE(provider, external_message_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_service_message_links_pending
  ON customer_service_message_links(provider, sync_status, updated_at);

CREATE TABLE IF NOT EXISTS customer_service_webhook_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL CHECK (provider IN ('chaskiq', 'tiledesk', 'papercups')),
  external_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'failed', 'ignored')),
  processing_error TEXT,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TEXT,
  UNIQUE(provider, external_event_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_service_webhook_events_status
  ON customer_service_webhook_events(status, received_at);
