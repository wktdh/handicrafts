CREATE TABLE IF NOT EXISTS platform_finance_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  service_fee_bps INTEGER NOT NULL DEFAULT 500 CHECK (service_fee_bps BETWEEN 0 AND 3000),
  updated_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO platform_finance_settings (id, service_fee_bps) VALUES (1, 500);

CREATE TABLE IF NOT EXISTS shop_wallets (
  shop_id TEXT PRIMARY KEY REFERENCES shops(id) ON DELETE CASCADE,
  available_cents INTEGER NOT NULL DEFAULT 0,
  pending_cents INTEGER NOT NULL DEFAULT 0,
  withdrawing_cents INTEGER NOT NULL DEFAULT 0,
  withdrawn_cents INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shop_settlements (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  order_id TEXT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE RESTRICT,
  gross_cents INTEGER NOT NULL CHECK (gross_cents >= 0),
  platform_fee_cents INTEGER NOT NULL CHECK (platform_fee_cents >= 0),
  net_cents INTEGER NOT NULL CHECK (net_cents >= 0),
  fee_rate_bps INTEGER NOT NULL CHECK (fee_rate_bps BETWEEN 0 AND 3000),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'available', 'reversed')),
  available_at TEXT,
  reversed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_settlements_shop_status ON shop_settlements(shop_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS shop_wallet_ledger (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  settlement_id TEXT REFERENCES shop_settlements(id) ON DELETE SET NULL,
  withdrawal_id TEXT,
  entry_type TEXT NOT NULL CHECK (entry_type IN ('order_pending', 'order_available', 'refund_reversal', 'withdrawal_requested', 'withdrawal_rejected', 'withdrawal_paid')),
  available_delta_cents INTEGER NOT NULL DEFAULT 0,
  pending_delta_cents INTEGER NOT NULL DEFAULT 0,
  withdrawing_delta_cents INTEGER NOT NULL DEFAULT 0,
  withdrawn_delta_cents INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_wallet_ledger_shop_date ON shop_wallet_ledger(shop_id, created_at DESC);

CREATE TABLE IF NOT EXISTS shop_withdrawal_requests (
  id TEXT PRIMARY KEY,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  applicant_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  recipient_type TEXT NOT NULL CHECK (recipient_type IN ('bank', 'wallet')),
  recipient_snapshot TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'paid')),
  reviewer_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  reviewer_note TEXT,
  reviewed_at TEXT,
  paid_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_withdrawals_queue ON shop_withdrawal_requests(status, created_at DESC);
