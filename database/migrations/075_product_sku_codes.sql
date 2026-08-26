-- SKU codes are searchable merchant identifiers. Give legacy blank codes a
-- generated value before enforcing a case-insensitive, platform-wide unique key.
UPDATE product_skus
SET sku_code = 'SKU-' || UPPER(HEX(RANDOMBLOB(6)))
WHERE sku_code IS NULL OR TRIM(sku_code) = '';

-- Retain the first historical occurrence and assign a new automatic code to
-- any later duplicate so existing databases can safely receive the constraint.
WITH ranked_skus AS (
  SELECT id,
         ROW_NUMBER() OVER (PARTITION BY sku_code COLLATE NOCASE ORDER BY id) AS occurrence
  FROM product_skus
)
UPDATE product_skus
SET sku_code = 'SKU-' || UPPER(HEX(RANDOMBLOB(6)))
WHERE id IN (SELECT id FROM ranked_skus WHERE occurrence > 1);

CREATE UNIQUE INDEX IF NOT EXISTS idx_product_skus_sku_code_unique
ON product_skus(sku_code COLLATE NOCASE);
