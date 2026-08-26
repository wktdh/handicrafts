ALTER TABLE products ADD COLUMN product_code TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_products_product_code
ON products(product_code)
WHERE product_code IS NOT NULL;
