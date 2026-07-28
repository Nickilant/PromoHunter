from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://promo:promo@db:5432/promo"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 10080
    status_window_hours: int = 24
    report_cooldown_minutes: int = 30
    seed_on_start: bool = False


settings = Settings()
