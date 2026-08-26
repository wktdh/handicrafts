ALTER TABLE products ADD COLUMN weight_grams INTEGER CHECK (weight_grams IS NULL OR weight_grams BETWEEN 1 AND 100000);

UPDATE products
SET weight_grams = 320
WHERE id = 'product-demo-cup' AND weight_grams IS NULL;
