-- CodeScope Database Migrations
-- V008: Add github_models_pat to profiles

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS github_models_pat TEXT;
