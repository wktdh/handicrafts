ALTER TABLE orders ADD COLUMN expires_at TEXT;
ALTER TABLE payment_transactions ADD COLUMN payment_token TEXT;
ALTER TABLE payment_transactions ADD COLUMN initiated_at TEXT;
ALTER TABLE payment_transactions ADD COLUMN failed_at TEXT;
ALTER TABLE payment_transactions ADD COLUMN failure_reason TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_transactions_token
  ON payment_transactions(payment_token);
