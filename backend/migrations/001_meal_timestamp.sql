-- Save when each meal was eaten so daily tracking works.
-- Only run on a database that does not already have consumed_at.
-- If existing meals have no dates, they will receive the migration time.
ALTER TABLE "Meals"
ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
