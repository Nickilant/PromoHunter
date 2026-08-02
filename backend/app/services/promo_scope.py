"""Охват акции по городам.

Акция принадлежит бренду, а не точке, — это ядро домена. Но одна и та же
сеть не всегда проводит акцию по всей стране, поэтому у акции есть список
городов и режим его чтения:

* ``exclude`` — акция идёт везде, кроме перечисленных городов. Пустой
  список означает федеральную акцию. Так удобно объявить акцию по всей
  стране и убрать её из пары городов, где сеть её не проводит, — не
  перечисляя вручную все остальные.
* ``include`` — акция идёт только в перечисленных городах.

Проверка нужна и в SQL (списки, каталог, лента), и в Python (по уже
загруженному объекту), поэтому обе формы живут рядом и обязаны совпадать.
"""

from sqlalchemy import and_, func, or_, select

from app.models import Promotion, PromotionCity, PromotionCityMode
from app.services.scope import city_key, normalize_city


def visible_in_city_clause(city: str):
    """Условие для запросов: акция показывается в этом городе."""
    listed = (
        select(PromotionCity.promotion_id)
        .where(
            PromotionCity.promotion_id == Promotion.id,
            func.lower(func.trim(PromotionCity.city)) == city_key(city),
        )
        .exists()
    )
    return or_(
        and_(Promotion.city_mode == PromotionCityMode.exclude, ~listed),
        and_(Promotion.city_mode == PromotionCityMode.include, listed),
    )


def promotion_visible_in(promotion: Promotion, city: str | None) -> bool:
    """То же самое по загруженному объекту."""
    listed = {city_key(row.city) for row in promotion.cities}
    key = city_key(city)
    if promotion.city_mode == PromotionCityMode.include:
        return key in listed
    return key not in listed


def describe_scope(promotion: Promotion) -> str:
    """Человекочитаемый охват — для админки и сообщений бота."""
    names = sorted(normalize_city(row.city) or "" for row in promotion.cities)
    if promotion.city_mode == PromotionCityMode.include:
        return ("только: " + ", ".join(names)) if names else "нигде не показывается"
    return ("везде, кроме: " + ", ".join(names)) if names else "вся страна"
