ALTER TABLE seller_profiles ADD COLUMN business_address TEXT;
ALTER TABLE seller_profiles ADD COLUMN payout_method TEXT;
ALTER TABLE seller_profiles ADD COLUMN payout_account TEXT;
ALTER TABLE seller_profiles ADD COLUMN operating_categories_json TEXT NOT NULL DEFAULT '[]';
