-- Existing Meals records did not store a date. Old rows will get the migration time.
-- Run this once against the same Neon database used by FastAPI.
ALTER TABLE "Meals"
ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
