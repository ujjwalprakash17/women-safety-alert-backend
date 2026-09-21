from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Defaulted (rather than required) so `uvicorn` can start and GET /health can
    # respond before real Supabase values exist in .env — only /me and Alembic
    # migrations need the real values filled in.
    DATABASE_URL: str = "postgresql+asyncpg://not-configured-yet"

    SUPABASE_URL: str = "https://not-configured-yet.supabase.co"
    SUPABASE_JWKS_URL: str = "https://not-configured-yet.supabase.co/auth/v1/.well-known/jwks.json"
    SUPABASE_JWT_AUD: str = "authenticated"

    # Only set if the Supabase project still uses the legacy HS256 shared secret
    # (Project Settings > API > JWT Settings tells you which mode is active).
    SUPABASE_JWT_SECRET: str | None = None

    FRONTEND_ORIGIN: str = "http://localhost:3000"


settings = Settings()
