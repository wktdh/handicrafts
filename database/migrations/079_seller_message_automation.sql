ALTER TABLE shop_messages ADD COLUMN automation_kind TEXT;

CREATE TABLE IF NOT EXISTS seller_message_settings (
  shop_id TEXT PRIMARY KEY REFERENCES shops(id) ON DELETE CASCADE,
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  weekly_hours_json TEXT NOT NULL DEFAULT '{"mon":[{"start":"09:00","end":"18:00"}],"tue":[{"start":"09:00","end":"18:00"}],"wed":[{"start":"09:00","end":"18:00"}],"thu":[{"start":"09:00","end":"18:00"}],"fri":[{"start":"09:00","end":"18:00"}],"sat":[],"sun":[]}',
  unanswered_minutes INTEGER NOT NULL DEFAULT 3 CHECK (unanswered_minutes BETWEEN 1 AND 60),
  off_hours_auto_reply_enabled INTEGER NOT NULL DEFAULT 1 CHECK (off_hours_auto_reply_enabled IN (0, 1)),
  off_hours_reply_template TEXT NOT NULL DEFAULT '店主当前处于非工作时间，已收到您的消息，请耐心等待，我们会在工作时间尽快回复您。',
  urgent_email_enabled INTEGER NOT NULL DEFAULT 1 CHECK (urgent_email_enabled IN (0, 1)),
  urgent_sms_enabled INTEGER NOT NULL DEFAULT 0 CHECK (urgent_sms_enabled IN (0, 1)),
  unanswered_email_enabled INTEGER NOT NULL DEFAULT 1 CHECK (unanswered_email_enabled IN (0, 1)),
  ai_reply_enabled INTEGER NOT NULL DEFAULT 1 CHECK (ai_reply_enabled IN (0, 1)),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seller_message_attention (
  message_id TEXT PRIMARY KEY REFERENCES shop_messages(id) ON DELETE CASCADE,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  buyer_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'high', 'urgent')),
  reason TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seller_message_notifications (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES shop_messages(id) ON DELETE CASCADE,
  shop_id TEXT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  seller_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL CHECK (notification_type IN ('unanswered', 'urgent')),
  channel TEXT NOT NULL CHECK (channel IN ('in_app', 'web_push', 'email', 'sms')),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
  due_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(message_id, notification_type, channel)
);

CREATE INDEX IF NOT EXISTS idx_seller_message_attention_shop_status
  ON seller_message_attention(shop_id, status, priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_seller_message_notifications_due
  ON seller_message_notifications(status, due_at, created_at);
