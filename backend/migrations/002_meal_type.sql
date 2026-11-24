-- Preserve the chosen meal section independently of its consumed timestamp.
ALTER TABLE "Meals" ADD COLUMN IF NOT EXISTS meal_type VARCHAR;
