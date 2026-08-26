-- Refund accounting: preserve the original settlement and track each reversal separately.
ALTER TABLE shop_wallets ADD COLUMN refund_debt_cents INTEGER NOT NULL DEFAULT 0
  CHECK (refund_debt_cents >= 0);
ALTER TABLE shop_settlements ADD COLUMN refunded_gross_cents INTEGER NOT NULL DEFAULT 0
  CHECK (refunded_gross_cents >= 0);
ALTER TABLE shop_settlements ADD COLUMN refunded_fee_cents INTEGER NOT NULL DEFAULT 0
  CHECK (refunded_fee_cents >= 0);
ALTER TABLE shop_settlements ADD COLUMN refunded_net_cents INTEGER NOT NULL DEFAULT 0
  CHECK (refunded_net_cents >= 0);

CREATE TABLE IF NOT EXISTS order_refunds (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
  after_sale_id TEXT UNIQUE REFERENCES after_sale_requests(id) ON DELETE SET NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  currency TEXT NOT NULL DEFAULT 'USD' CHECK (currency = 'USD'),
  exchange_rate TEXT NOT NULL DEFAULT '1.00000000',
  platform_fee_reversal_cents INTEGER NOT NULL DEFAULT 0 CHECK (platform_fee_reversal_cents >= 0),
  seller_net_reversal_cents INTEGER NOT NULL DEFAULT 0 CHECK (seller_net_reversal_cents >= 0),
  status TEXT NOT NULL DEFAULT 'recorded' CHECK (status IN ('recorded', 'succeeded', 'failed')),
  provider_reference TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_order_refunds_order ON order_refunds(order_id, status, created_at DESC);

-- Logistics providers post signed delivery updates here. The event id makes webhook retries idempotent.
ALTER TABLE shipments ADD COLUMN logistics_provider TEXT;
ALTER TABLE shipments ADD COLUMN provider_tracking_id TEXT;
ALTER TABLE shipments ADD COLUMN last_tracking_status TEXT;
ALTER TABLE shipments ADD COLUMN last_tracking_at TEXT;

CREATE TABLE IF NOT EXISTS logistics_webhook_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  external_event_id TEXT NOT NULL,
  shipment_id TEXT REFERENCES shipments(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, external_event_id)
);
CREATE INDEX IF NOT EXISTS idx_logistics_webhook_shipment ON logistics_webhook_events(shipment_id, received_at DESC);
