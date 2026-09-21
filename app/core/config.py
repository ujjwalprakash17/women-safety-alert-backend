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

    # Comma-separated so the same deployed backend can serve both a local
    # dev frontend and a deployed one (e.g. Vercel) at the same time.
    FRONTEND_ORIGINS: str = "http://localhost:3000"

    @property
    def frontend_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]

    # Web Push (VAPID). No fake placeholder for the private key on purpose —
    # code checks `if settings.VAPID_PRIVATE_KEY:` before ever calling
    # webpush(), so "not configured" is an explicit, obvious no-op rather
    # than a confusing failed call.
    VAPID_PRIVATE_KEY: str | None = None  # path to private_key.pem
    VAPID_PUBLIC_KEY: str = ""  # base64url application-server key
    VAPID_CONTACT_EMAIL: str = "mailto:admin@example.com"


settings = Settings()
