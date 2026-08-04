ALTER TABLE products ADD COLUMN supports_custom INTEGER NOT NULL DEFAULT 1
  CHECK (supports_custom IN (0, 1));
