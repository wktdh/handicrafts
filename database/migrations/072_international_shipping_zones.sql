-- International checkout needs the destination country to select a seller's shipping zone.
ALTER TABLE buyer_addresses ADD COLUMN country_code TEXT NOT NULL DEFAULT 'US'
  CHECK (length(country_code) = 2);
ALTER TABLE buyer_addresses ADD COLUMN country_name TEXT NOT NULL DEFAULT 'United States';

-- Preserve the exact delivery rule quoted at checkout. Seller changes must not alter an existing order.
ALTER TABLE orders ADD COLUMN shipping_rule_snapshot_json TEXT NOT NULL DEFAULT '{}';
