-- Keep existing deployments aligned with the published 5% platform commission.
UPDATE platform_finance_settings
SET service_fee_bps = 500,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
