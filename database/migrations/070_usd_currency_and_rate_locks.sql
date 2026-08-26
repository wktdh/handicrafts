-- USD is the platform's single transaction and settlement currency.
ALTER TABLE products ADD COLUMN price_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (price_currency = 'USD');

ALTER TABLE orders ADD COLUMN pricing_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (pricing_currency = 'USD');
ALTER TABLE orders ADD COLUMN payment_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (payment_currency = 'USD');
ALTER TABLE orders ADD COLUMN settlement_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (settlement_currency = 'USD');
ALTER TABLE orders ADD COLUMN payment_exchange_rate TEXT NOT NULL DEFAULT '1.00000000';
ALTER TABLE orders ADD COLUMN settlement_exchange_rate TEXT NOT NULL DEFAULT '1.00000000';

ALTER TABLE order_items ADD COLUMN price_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (price_currency = 'USD');

ALTER TABLE payment_transactions ADD COLUMN payment_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (payment_currency = 'USD');
ALTER TABLE payment_transactions ADD COLUMN exchange_rate TEXT NOT NULL DEFAULT '1.00000000';

ALTER TABLE shop_settlements ADD COLUMN settlement_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (settlement_currency = 'USD');
ALTER TABLE shop_settlements ADD COLUMN settlement_exchange_rate TEXT NOT NULL DEFAULT '1.00000000';

ALTER TABLE after_sale_requests ADD COLUMN refund_currency TEXT NOT NULL DEFAULT 'USD'
  CHECK (refund_currency = 'USD');
ALTER TABLE after_sale_requests ADD COLUMN refund_exchange_rate TEXT NOT NULL DEFAULT '1.00000000';
