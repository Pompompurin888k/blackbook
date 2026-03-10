-- Migration: Add provider story columns
-- (migrated from repo root migrations/003_add_provider_stories.sql)

ALTER TABLE providers
ADD COLUMN IF NOT EXISTS story_photo VARCHAR(255),
ADD COLUMN IF NOT EXISTS story_created_at TIMESTAMP WITH TIME ZONE;
