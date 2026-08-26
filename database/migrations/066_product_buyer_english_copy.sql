ALTER TABLE products ADD COLUMN buyer_title TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN buyer_description TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN buyer_material TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN buyer_seo_tags_json TEXT NOT NULL DEFAULT '[]';
