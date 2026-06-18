import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Calibrate"
    database_url: str = "sqlite:///./calibrate.db"

    # Signs session cookies. MUST be set to a stable secret in production —
    # a random default means sessions reset on every restart.
    secret_key: str = secrets.token_urlsafe(32)

    # USDA FoodData Central. Optional — Open Food Facts works without it.
    fdc_api_key: str | None = None


settings = Settings()
