ALTER TABLE seller_verification_applications ADD COLUMN business_type TEXT NOT NULL DEFAULT 'individual'
  CHECK (business_type IN ('individual', 'enterprise'));
ALTER TABLE seller_verification_applications ADD COLUMN legal_representative TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN business_license_no TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN business_address TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN expires_at TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN rejection_code TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN resubmission_of TEXT REFERENCES seller_verification_applications(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS seller_verification_documents (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES seller_verification_applications(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL CHECK (document_type IN ('identity_front', 'identity_back', 'business_license', 'authorization', 'other')),
  file_url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
  reviewer_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_verification_documents_application ON seller_verification_documents(application_id, created_at);

CREATE TABLE IF NOT EXISTS shop_staff_audit_logs (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  staff_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  actor_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  action TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_staff_audit_shop ON shop_staff_audit_logs(shop_id, created_at DESC);

CREATE TABLE IF NOT EXISTS campaign_audiences (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE CASCADE,
  buyer_user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  segment TEXT,
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (buyer_user_id IS NOT NULL OR segment IS NOT NULL),
  UNIQUE(campaign_id, buyer_user_id, segment)
);
CREATE INDEX IF NOT EXISTS idx_campaign_audiences_campaign ON campaign_audiences(campaign_id);

CREATE TABLE IF NOT EXISTS campaign_coupon_codes (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES platform_campaigns(id) ON DELETE CASCADE,
  code TEXT NOT NULL UNIQUE,
  assigned_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'issued' CHECK (status IN ('issued', 'redeemed', 'expired', 'disabled')),
  expires_at TEXT,
  redeemed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_campaign_coupon_codes_campaign ON campaign_coupon_codes(campaign_id, status, expires_at);

CREATE TABLE IF NOT EXISTS platform_activities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'active', 'ended')),
  starts_at TEXT,
  ends_at TEXT,
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_page_configs (
  id TEXT PRIMARY KEY,
  activity_id TEXT NOT NULL UNIQUE REFERENCES platform_activities(id) ON DELETE CASCADE,
  banner_url TEXT,
  theme_json TEXT NOT NULL DEFAULT '{}',
  modules_json TEXT NOT NULL DEFAULT '[]',
  updated_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_applications (
  id TEXT PRIMARY KEY,
  activity_id TEXT NOT NULL REFERENCES platform_activities(id) ON DELETE CASCADE,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  applicant_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
  reviewer_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  review_note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at TEXT,
  UNIQUE(activity_id, shop_id)
);

CREATE TABLE IF NOT EXISTS activity_products (
  id TEXT PRIMARY KEY,
  activity_id TEXT NOT NULL REFERENCES platform_activities(id) ON DELETE CASCADE,
  application_id TEXT NOT NULL REFERENCES activity_applications(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  quota_stock INTEGER NOT NULL CHECK (quota_stock >= 0),
  reserved_stock INTEGER NOT NULL DEFAULT 0 CHECK (reserved_stock >= 0),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'active', 'disabled')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(activity_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_activity_products_product ON activity_products(product_id, status);

CREATE TABLE IF NOT EXISTS search_synonyms (
  id TEXT PRIMARY KEY,
  source_term TEXT NOT NULL UNIQUE,
  target_terms_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS search_corrections (
  id TEXT PRIMARY KEY,
  typo TEXT NOT NULL UNIQUE,
  corrected_term TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS search_recommendations (
  id TEXT PRIMARY KEY,
  keyword TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  weight INTEGER NOT NULL DEFAULT 100,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(keyword, recommendation)
);
CREATE TABLE IF NOT EXISTS search_zero_result_rules (
  id TEXT PRIMARY KEY,
  keyword TEXT NOT NULL UNIQUE,
  message TEXT NOT NULL,
  product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS search_query_metrics (
  id TEXT PRIMARY KEY,
  keyword TEXT NOT NULL,
  corrected_keyword TEXT,
  result_count INTEGER NOT NULL,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_search_query_metrics_keyword ON search_query_metrics(keyword, created_at DESC);
