CREATE INDEX IF NOT EXISTS idx_analytics_events_actor_funnel
  ON analytics_events(user_id, visitor_key, created_at, event_type);
CREATE INDEX IF NOT EXISTS idx_orders_channel_paid
  ON orders(attribution_channel, paid_at, status);
CREATE INDEX IF NOT EXISTS idx_orders_buyer_paid
  ON orders(buyer_user_id, paid_at, status);
