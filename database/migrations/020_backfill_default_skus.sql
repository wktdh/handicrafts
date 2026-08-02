INSERT OR IGNORE INTO product_skus (id, product_id, price_cents, stock, option_value_ids, status)
SELECT products.id || '-default-sku', products.id, products.price_cents, products.stock, '[]', 'active'
FROM products
WHERE NOT EXISTS (
  SELECT 1 FROM product_skus WHERE product_skus.product_id = products.id
);
