-- CodeScope Database Migrations
-- V009: Add custom OpenAI-compatible API endpoint support to profiles

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_api_url TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_api_key TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS custom_api_model TEXT;
