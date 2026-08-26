INSERT OR IGNORE INTO users (id, display_name, phone, password_hash)
VALUES ('user-demo-buyer', '林知夏', '13800000000', 'replace-with-argon2-hash');

INSERT OR IGNORE INTO users (id, display_name, email, password_hash)
VALUES ('user-demo-seller', '陶然物语', 'seller@example.test', 'replace-with-argon2-hash');

INSERT OR IGNORE INTO users (id, display_name, phone, email, password_hash)
VALUES ('user-platform-admin', '平台管理员', '13800000002', 'admin@example.test', 'platform-admin');

-- Preserve a real administrator phone when one has been configured, while
-- making the development admin usable with the SMS step-up flow.
UPDATE users
SET phone = '13800000002'
WHERE id = 'user-platform-admin' AND (phone IS NULL OR phone = '');

INSERT OR IGNORE INTO platform_admins (user_id) VALUES ('user-platform-admin');

INSERT OR IGNORE INTO user_roles (user_id, role) VALUES
  ('user-demo-buyer', 'buyer'),
  ('user-demo-seller', 'seller');

INSERT OR IGNORE INTO seller_profiles (user_id, verification_status, contact_phone)
VALUES ('user-demo-seller', 'approved', '13800000001');

INSERT OR IGNORE INTO shops (id, owner_user_id, name, description, location)
VALUES (
  'shop-demo-taoran',
  'user-demo-seller',
  '陶然物语',
  '专注于日用陶器的独立手作店。',
  '杭州'
);

INSERT OR IGNORE INTO products (
  id, shop_id, product_code, category, title, description, material, weight_grams, dimensions, price_cents, stock, status, published_at
) VALUES (
  'product-demo-cup',
  'shop-demo-taoran',
  'DEMO2026',
  '陶艺',
  '山岚手作陶瓷咖啡杯',
  '每只杯子由陶艺师手工拉坯、上釉与烧制。',
  '高白泥、无铅釉',
  320,
  '12 × 8 × 9 cm',
  16800,
  12,
  'published',
  CURRENT_TIMESTAMP
);

-- The buyer-facing catalogue uses these localized fields for public search
-- and product cards. Keep the seeded listing discoverable in the E2E locale
-- as well as through its maker-facing source fields.
UPDATE products
SET
  buyer_title = 'Handmade ceramic coffee cup',
  buyer_description = 'A wheel-thrown ceramic coffee cup, glazed and fired by hand.',
  buyer_material = 'High-white clay, lead-free glaze',
  buyer_seo_tags_json = '["ceramic", "coffee", "cup", "handmade"]'
WHERE id = 'product-demo-cup'
  AND buyer_title = '';

-- Kept separate from the public search fixture because moderation tests
-- intentionally unlist their target product.
INSERT OR IGNORE INTO products (
  id, shop_id, product_code, category, title, description, material,
  price_cents, stock, status, published_at
) VALUES (
  'product-e2e-moderation',
  'shop-demo-taoran',
  'MODTEST2026',
  '陶艺',
  '审核流程测试商品',
  '仅用于端到端审核流程验证。',
  '陶土',
  100,
  1,
  'published',
  CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO product_media (id, product_id, media_type, storage_key, public_url, sort_order, is_cover)
VALUES (
  'media-demo-cup-cover',
  'product-demo-cup',
  'image',
  'seed/products/cup-cover.jpg',
  'local://ceramic-cup.jpg',
  0,
  1
);

INSERT OR IGNORE INTO product_skus (id, product_id, price_cents, stock, option_value_ids, status)
SELECT products.id || '-default-sku', products.id, products.price_cents, products.stock, '[]', 'active'
FROM products
WHERE NOT EXISTS (
  SELECT 1 FROM product_skus WHERE product_skus.product_id = products.id
);
