from functools import lru_cache
from app.config import Settings, settings as app_settings
from app.repositories.supabase import SupabaseRepository

@lru_cache
def get_settings() -> Settings:
    return app_settings

async def get_supabase_repo() -> SupabaseRepository:
    settings = get_settings()
    repo = SupabaseRepository(settings)
    yield repo
    await repo.close()
