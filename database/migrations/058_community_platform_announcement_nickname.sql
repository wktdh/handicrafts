UPDATE community_posts
SET nickname = '平台管理员', updated_at = CURRENT_TIMESTAMP
WHERE category = '平台公告';
