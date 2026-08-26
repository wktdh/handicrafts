ALTER TABLE media_assets ADD COLUMN verified_at TEXT;
ALTER TABLE media_assets ADD COLUMN moderation_status TEXT NOT NULL DEFAULT 'pending'
  CHECK (moderation_status IN ('pending', 'approved', 'rejected'));
ALTER TABLE product_media ADD COLUMN asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL;
ALTER TABLE product_option_values ADD COLUMN asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_product_media_asset ON product_media(asset_id);
CREATE INDEX IF NOT EXISTS idx_product_option_value_asset ON product_option_values(asset_id);
