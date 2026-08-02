CREATE TABLE IF NOT EXISTS media_assets (
  id TEXT PRIMARY KEY,
  uploader_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  media_type TEXT NOT NULL CHECK (media_type IN ('image', 'video')),
  mime_type TEXT NOT NULL,
  storage_key TEXT NOT NULL UNIQUE,
  public_url TEXT NOT NULL UNIQUE,
  byte_size INTEGER NOT NULL CHECK (byte_size > 0),
  status TEXT NOT NULL DEFAULT 'temporary' CHECK (status IN ('temporary', 'active', 'blocked', 'deleted')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS media_asset_links (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'report', 'appeal', 'after_sale', 'review', 'shop')),
  target_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (asset_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_media_assets_cleanup
  ON media_assets(status, created_at);
CREATE INDEX IF NOT EXISTS idx_media_asset_links_target
  ON media_asset_links(target_type, target_id);
