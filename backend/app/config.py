from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://promo:promo@db:5432/promo"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 10080
    status_window_hours: int = 24
    report_cooldown_minutes: int = 30
    seed_on_start: bool = False

    # --- сила голоса (см. docs/trust-and-rating-spec.md) ---
    vote_half_life_hours: float = 4.0     # полураспад свежести голоса
    channel_on_site_coef: float = 1.0
    channel_delivery_yes_coef: float = 0.75  # «мне привезли» — сильный сигнал
    channel_delivery_no_coef: float = 0.35   # «в меню доставки нет» — слабый

    # --- переключение статусов ---
    flip_ratio: float = 1.5               # перевес массы для полного переключения
    stale_flip_hours: float = 2.0         # старше — данные «протухли», флип одним голосом

    # --- веса пользователей (скрытые) ---
    weight_min: float = 0.1
    weight_max: float = 10.0
    weight_confirm_bonus: float = 0.1
    weight_pioneer_bonus: float = 0.3
    weight_refute_factor: float = 0.5
    weight_drift_monthly: float = 0.10    # дрейф к 1.0 при неактивности

    # --- вердикты ---
    verdict_mature_hours: int = 12        # дозревание отчёта
    consensus_window_hours: int = 3       # окно сравнения ±N часов
    consensus_min_mass: float = 1.0       # меньше — консенсуса нет, вердикт нейтрален

    # --- рейтинг ---
    rating_base_points: int = 1
    rating_confirmed_points: int = 5
    rating_pioneer_points: int = 15
    rating_scout_points: int = 5
    rating_suggestion_points: int = 20
    rating_refuted_points: int = -5
    rating_spam_points: int = -10
    rating_daily_base_cap: int = 10       # отчётов в день с базовыми очками

    # --- фоновый пересчёт ---
    trust_job_interval_seconds: int = 300  # 0 — выключить фоновую джобу


settings = Settings()
