ALTER TABLE admin_step_up_tickets
  ADD COLUMN session_token_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_admin_step_up_tickets_session
  ON admin_step_up_tickets(session_token_hash, expires_at DESC);
