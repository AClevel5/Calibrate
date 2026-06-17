from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Calibrate"
    database_url: str = "sqlite:///./calibrate.db"

    # USDA FoodData Central. Optional — Open Food Facts works without it.
    fdc_api_key: str | None = None

    # Optional bearer token guarding the Apple Health ingest endpoint.
    health_ingest_token: str | None = None


settings = Settings()
