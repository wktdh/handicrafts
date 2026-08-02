CREATE TABLE media_asset_links_new (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN ('product', 'report', 'appeal', 'after_sale', 'review', 'shop', 'message')),
  target_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (asset_id, target_type, target_id)
);

INSERT INTO media_asset_links_new (id, asset_id, target_type, target_id, created_at)
  SELECT id, asset_id, target_type, target_id, created_at FROM media_asset_links;

DROP TABLE media_asset_links;
ALTER TABLE media_asset_links_new RENAME TO media_asset_links;

CREATE INDEX IF NOT EXISTS idx_media_asset_links_target
  ON media_asset_links(target_type, target_id);
