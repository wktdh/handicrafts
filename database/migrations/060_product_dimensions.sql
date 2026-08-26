ALTER TABLE products ADD COLUMN dimensions TEXT CHECK (dimensions IS NULL OR length(dimensions) <= 100);

UPDATE products
SET dimensions = '12 × 8 × 9 cm'
WHERE id = 'product-demo-cup' AND dimensions IS NULL;
