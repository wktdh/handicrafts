UPDATE products
SET category = '微缩景观'
WHERE category = '苔藓微景观';

UPDATE seller_profiles
SET operating_categories_json = REPLACE(operating_categories_json, '苔藓微景观', '微缩景观')
WHERE operating_categories_json LIKE '%苔藓微景观%';
