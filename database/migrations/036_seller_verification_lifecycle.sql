ALTER TABLE seller_profiles ADD COLUMN verification_expires_at TEXT;
ALTER TABLE seller_profiles ADD COLUMN verification_expiry_notified_at TEXT;

ALTER TABLE seller_verification_applications ADD COLUMN supplement_requested_at TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN supplement_due_at TEXT;
ALTER TABLE seller_verification_applications ADD COLUMN review_round INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_seller_profiles_verification_expiry
  ON seller_profiles(verification_status, verification_expires_at);
CREATE INDEX IF NOT EXISTS idx_seller_verification_supplement_due
  ON seller_verification_applications(status, supplement_due_at);
