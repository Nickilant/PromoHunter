from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://promo:promo@db:5432/promo"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 10080
    status_window_hours: int = 24
    report_cooldown_minutes: int = 30
    suggestion_cooldown_minutes: int = 15
    issue_cooldown_minutes: int = 5
    promo_code_vote_cooldown_seconds: int = 60
    seed_on_start: bool = False
    upload_dir: str = "uploads"

    # --- сила голоса при дозревании вердиктов (см. docs/trust-and-rating-spec.md) ---
    channel_on_site_coef: float = 1.0
    channel_delivery_yes_coef: float = 0.75  # «мне привезли» — сильный сигнал
    channel_delivery_no_coef: float = 0.35   # «в меню доставки нет» — слабый
    flip_ratio: float = 1.5               # перевес массы для консенсуса вердикта

    # --- определение истины (app/services/truth.py) ---
    truth_half_life_hours: float = 3.0    # полураспад накопленных лог-шансов
    truth_k_on_site: float = 1.8          # свидетельство с точки
    truth_k_receipt: float = 3.0          # «есть» с чеком — человек это купил
    truth_k_delivery_yes: float = 1.4     # «мне привезли» — сигнал о прошлом
    truth_k_delivery_no: float = 0.7      # «в меню доставки нет» — не о зале
    truth_trust_min: float = 0.5          # границы множителя доверия
    truth_trust_max: float = 1.5
    truth_ceiling_base: float = 2.6       # потолок уверенности на тихой точке
    truth_ceiling_slope: float = 0.9      # прирост потолка от ln(плотности)
    truth_ceiling_max: float = 7.0
    truth_density_window_minutes: int = 60  # окно, по которому меряется плотность
    truth_p_available: float = 0.85       # порог уверенного «есть»
    truth_p_unavailable: float = 0.15     # порог уверенного «кончилось»

    # --- уведомления о переключении статуса ---
    notify_dwell_minutes: float = 10.0        # выдержка перед уведомлением
    notify_dwell_window_minutes: float = 20.0  # окно, в котором она копится
    # Пол против дребезга. Длинная пауза здесь вредна: «кончилось» через
    # полчаса после «появилось» — это правда, а не спам, и подписчик должен
    # её получить. Основную защиту даёт выдержка, а не кулдаун.
    notify_cooldown_minutes: float = 20.0

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

    # --- промокоды (отдельная сущность, см. services/promo_code.py) ---
    promo_code_ttl_days: float = 5.0          # столько живёт код без подтверждений
    # Пол продления: n-е подтверждение одного человека даёт ttl / 2^(n-1),
    # но не меньше этого — держать код в одиночку можно, но дёшево не выйдет
    promo_code_ttl_floor_hours: float = 12.0
    promo_code_fail_votes: int = 2            # столько разных жалоб убивают код
    promo_code_author_points: int = 5         # автору, один раз за жизнь кода
    promo_code_daily_limit: int = 10          # сколько кодов человек добавит за сутки

    # --- фоновый пересчёт ---
    trust_job_interval_seconds: int = 300  # 0 — выключить фоновую джобу

    # --- Telegram (WebApp-авторизация, бот-уведомления, подтверждение номера) ---
    telegram_bot_token: str = ""  # пусто — телеграм-функции выключены
    telegram_polling_enabled: bool = True  # бот слушает сообщения (подтверждение номера)
    phone_code_ttl_minutes: int = 10       # срок жизни кода подтверждения
    phone_code_resend_seconds: int = 60    # кулдаун повторного запроса кода
    phone_code_max_attempts: int = 5       # попыток ввода кода
    # Требовать подтверждённый номер для отчётов/заявок/подписок.
    # По умолчанию выключено — локальная разработка работает без Telegram.
    require_phone_verification: bool = False

    # --- игровой режим: захват точек фракциями (docs/game-mode-spec.md) ---
    game_enabled: bool = True  # выключатель фичи на весь сервис
    game_job_interval_seconds: int = 60  # 0 — выключить фоновый пересчёт шкал

    # чек ФНС
    receipt_min_sum_kopeks: int = 5000        # 50 ₽ — ниже не считаем покупкой
    # Чек печатают сразу после оплаты, а заказ отдают позже — окно считаем
    # от кассы до момента, когда человек увидел, что ему досталось
    receipt_max_age_minutes: int = 30
    receipt_future_tolerance_minutes: int = 5  # часы кассы могут спешить
    # Насколько присланный телефоном часовой пояс может расходиться с
    # оценкой по долготе точки, прежде чем мы перестанем ему верить
    receipt_offset_slack_minutes: int = 150
    receipt_max_i_rate_per_minute: float = 20.0   # предел скорости счётчика ФД
    receipt_bind_confirmations: int = 3       # подтверждений привязки fn к точке
    receipt_bind_ttl_days: int = 365          # срок жизни привязки fn
    capture_geo_radius_m: float = 800.0       # радиус приёма чека от обычного пользователя
    capture_require_geo: bool = True

    # сила фракции на точке
    capture_half_life_hours: float = 72.0     # полураспад силы (у обеих сторон)
    # Убывающая отдача: 1-й чек пользователя за сутки на точке, 2-й, 3-й, далее
    capture_daily_returns: list[float] = [1.0, 0.5, 0.25, 0.1]
    capture_underdog_max_bonus: float = 0.25  # до +25% слабейшей фракции города
    capture_min_score: float = 0.5            # ниже — сторона в игре не считается

    # шкалы захвата
    capture_bar_seconds: int = 14400          # 4 часа при равной силе
    capture_bar_max_speed: float = 2.4        # при перевесе — до 1 ч 40 мин
    capture_bar_speed_lead_span: float = 3.0  # перевес, где скорость максимальна
    capture_paused_decay_per_hour: float = 0.10  # шкала на паузе подтаивает
    capture_truce_hours: float = 2.0          # перемирие после отбитой атаки
    capture_battle_max_hours: float = 48.0    # висящая битва сбрасывается
    capture_active_hours_min_receipts: int = 20  # с этого объёма верим часам точки

    # уведомления об атаке
    capture_attack_notify_cooldown_hours: float = 3.0
    capture_attack_warning_minutes: float = 30.0  # финальное предупреждение

    # баланс фракций
    faction_join_block_share: float = 0.60    # набор закрыт при такой доле в городе
    faction_switch_days: int = 30             # как часто можно менять сторону

    # очки за игру
    rating_capture_receipt_points: int = 25   # за чек (с той же убывающей отдачей)
    rating_capture_win_points: int = 10       # участнику победившей стороны
    rating_capture_finisher_points: int = 15  # тому, чей чек закрыл шкалу

    # ретроградная переоценка «нет» чеком
    weight_receipt_refute_factor: float = 0.7  # мягче обычного 0.5
    receipt_refute_window_minutes: int = 45


settings = Settings()
