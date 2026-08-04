ALTER TABLE community_comments ADD COLUMN parent_comment_id TEXT REFERENCES community_comments(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_community_comments_parent ON community_comments(parent_comment_id, status, created_at);
