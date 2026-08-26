ALTER TABLE admin_step_up_tickets
  ADD COLUMN scope TEXT NOT NULL DEFAULT 'standard'
  CHECK (scope IN ('standard', 'high_risk'));
