CREATE TABLE IF NOT EXISTS governance_case_notes (
  id TEXT PRIMARY KEY,
  case_type TEXT NOT NULL CHECK (case_type IN ('report', 'appeal', 'product')),
  case_id TEXT NOT NULL,
  author_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 1000),
  visibility TEXT NOT NULL DEFAULT 'internal' CHECK (visibility IN ('internal', 'external')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_case_notes_case
  ON governance_case_notes(case_type, case_id, created_at);

CREATE TABLE IF NOT EXISTS support_tickets (
  id TEXT PRIMARY KEY,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  shop_id TEXT REFERENCES shops(id) ON DELETE SET NULL,
  order_id TEXT REFERENCES orders(id) ON DELETE SET NULL,
  subject TEXT NOT NULL CHECK (length(subject) BETWEEN 1 AND 120),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
  assigned_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_buyer ON support_tickets(buyer_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_shop ON support_tickets(shop_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS support_ticket_messages (
  id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  sender_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  sender_role TEXT NOT NULL CHECK (sender_role IN ('buyer', 'seller', 'admin')),
  content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 1000),
  attachment_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_ticket_messages_ticket
  ON support_ticket_messages(ticket_id, created_at);

CREATE TABLE IF NOT EXISTS seller_verification_applications (
  id TEXT PRIMARY KEY,
  seller_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  legal_name TEXT NOT NULL CHECK (length(legal_name) BETWEEN 2 AND 80),
  identity_number TEXT NOT NULL CHECK (length(identity_number) BETWEEN 6 AND 32),
  contact_phone TEXT NOT NULL CHECK (length(contact_phone) BETWEEN 6 AND 20),
  evidence_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  reviewer_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  review_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_seller_verification_queue
  ON seller_verification_applications(status, created_at DESC);

CREATE TABLE IF NOT EXISTS shop_staff (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('operator', 'fulfillment', 'customer_service')),
  permissions_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  invited_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shop_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_shop_staff_user ON shop_staff(user_id, status);

CREATE TABLE IF NOT EXISTS database_backup_runs (
  id TEXT PRIMARY KEY,
  file_name TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  restored_at TEXT,
  restored_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL
);

ALTER TABLE seller_quick_replies ADD COLUMN category TEXT NOT NULL DEFAULT 'general';

CREATE TABLE media_asset_links_new (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'report', 'appeal', 'after_sale', 'review', 'shop', 'message', 'support_ticket', 'seller_verification')),
  target_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (asset_id, target_type, target_id)
);

INSERT INTO media_asset_links_new (id, asset_id, target_type, target_id, created_at)
  SELECT id, asset_id, target_type, target_id, created_at FROM media_asset_links;

DROP TABLE media_asset_links;
ALTER TABLE media_asset_links_new RENAME TO media_asset_links;
CREATE INDEX IF NOT EXISTS idx_media_asset_links_target ON media_asset_links(target_type, target_id);
