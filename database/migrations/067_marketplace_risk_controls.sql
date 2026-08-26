CREATE TABLE risk_cases (
  id TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL CHECK (category IN ('coupon_abuse', 'order_anomaly', 'wash_trading', 'refund_dispute', 'image_duplicate')),
  severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'resolved', 'dismissed')),
  subject_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  order_id TEXT REFERENCES orders(id) ON DELETE SET NULL,
  product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
  reason_code TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  occurrences INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT,
  resolved_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  resolution_note TEXT
);

CREATE INDEX idx_risk_cases_queue ON risk_cases(status, severity, last_seen_at DESC);
CREATE INDEX idx_risk_cases_subject ON risk_cases(subject_user_id, category, last_seen_at DESC);

ALTER TABLE media_assets ADD COLUMN content_hash TEXT;
CREATE INDEX idx_media_assets_content_hash ON media_assets(content_hash) WHERE content_hash IS NOT NULL;

CREATE TABLE product_image_fingerprints (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  media_url TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(product_id, media_url)
);

CREATE INDEX idx_product_image_fingerprints_hash ON product_image_fingerprints(content_hash);

ALTER TABLE after_sale_evidence ADD COLUMN content_hash TEXT;
ALTER TABLE after_sale_evidence ADD COLUMN byte_size INTEGER;

CREATE TABLE after_sale_case_events (
  id TEXT PRIMARY KEY,
  after_sale_id TEXT NOT NULL REFERENCES after_sale_requests(id) ON DELETE CASCADE,
  actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  evidence_hashes_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_after_sale_case_events ON after_sale_case_events(after_sale_id, created_at);
