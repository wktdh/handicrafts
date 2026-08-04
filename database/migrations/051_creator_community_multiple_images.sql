CREATE TABLE IF NOT EXISTS community_post_images (
  id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (post_id, image_url)
);

CREATE TABLE IF NOT EXISTS community_comment_images (
  id TEXT PRIMARY KEY,
  comment_id TEXT NOT NULL REFERENCES community_comments(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (comment_id, image_url)
);

CREATE INDEX IF NOT EXISTS idx_community_post_images ON community_post_images(post_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_community_comment_images ON community_comment_images(comment_id, sort_order);
