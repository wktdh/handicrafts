ALTER TABLE support_tickets
  ADD COLUMN requester_role TEXT NOT NULL DEFAULT 'buyer'
  CHECK (requester_role IN ('buyer', 'seller'));

CREATE INDEX IF NOT EXISTS idx_support_tickets_requester
  ON support_tickets(buyer_user_id, requester_role, updated_at DESC);
