-- The platform's published commission is 4%. Keep existing deployments in
-- sync with the new-install default in 042_seller_finance.sql.
UPDATE platform_finance_settings
SET service_fee_bps = 400,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
