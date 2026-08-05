"""Получение точек OpenStreetMap для ручного административного импорта."""

import re
from dataclasses import dataclass

import httpx

from app.config import settings


class OsmError(ValueError):
    pass


@dataclass(frozen=True)
class OsmPoint:
    osm_type: str
    osm_id: int
    title: str | None
    address: str
    lat: float
    lng: float


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.osm_user_agent, "Accept": "application/json"},
        timeout=httpx.Timeout(40.0, connect=10.0),
        follow_redirects=True,
    )


def _city_bbox(city: str) -> tuple[float, float, float, float]:
    try:
        with _client() as client:
            response = client.get(
                f"{settings.osm_nominatim_url.rstrip('/')}/search",
                params={"q": city, "countrycodes": "ru", "format": "jsonv2", "limit": 5},
            )
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OsmError("Не удалось определить границы города через OpenStreetMap") from error
    row = next((item for item in rows if item.get("type") in {"city", "town", "municipality", "administrative"}), None)
    if row is None or len(row.get("boundingbox", [])) != 4:
        raise OsmError("Город не найден в OpenStreetMap — уточните его название")
    south, north, west, east = (float(value) for value in row["boundingbox"])
    return south, west, north, east


def _address(tags: dict[str, str]) -> str:
    street = tags.get("addr:street") or tags.get("addr:place")
    number = tags.get("addr:housenumber")
    parts = [part for part in (street, number) if part]
    if parts:
        return ", ".join(parts)[:300]
    return (tags.get("addr:full") or "Адрес не указан в OSM")[:300]


def _search_pattern(query: str) -> str:
    """Нечувствительный к оформлению шаблон названия.

    В OSM один и тот же бренд встречается с дефисом, длинным тире,
    типографским апострофом и без них. Ищем слова в исходном порядке, разрешая
    между ними любые разделители, но не превращаем запрос в набор отдельных
    несвязанных совпадений.
    """
    words = re.findall(r"\w+", query, flags=re.UNICODE)
    if not words:
        raise OsmError("Введите название бренда буквами или цифрами")
    return ".*".join(re.escape(word) for word in words)


def find_restaurants(city: str, query: str) -> list[OsmPoint]:
    south, west, north, east = _city_bbox(city)
    pattern = _search_pattern(query.strip())
    bbox = f"{south},{west},{north},{east}"
    overpass_query = f"""
[out:json][timeout:35];
(
  nwr[~\"^(name|name:ru|brand|operator|official_name|short_name)$\"~\"{pattern}\",i]({bbox});
);
out center tags;
"""
    try:
        with _client() as client:
            response = client.post(
                settings.osm_overpass_url,
                content=overpass_query.encode(),
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            response.raise_for_status()
            elements = response.json().get("elements", [])
    except (httpx.HTTPError, ValueError) as error:
        raise OsmError("OpenStreetMap сейчас не ответил — попробуйте немного позже") from error

    points: list[OsmPoint] = []
    for element in elements[: settings.osm_import_limit]:
        center = element.get("center") or element
        lat, lng = center.get("lat"), center.get("lon")
        if lat is None or lng is None:
            continue
        tags = element.get("tags") or {}
        points.append(
            OsmPoint(
                osm_type=str(element.get("type", "node"))[:12],
                osm_id=int(element["id"]),
                title=(tags.get("name") or query)[:200],
                address=_address(tags),
                lat=float(lat),
                lng=float(lng),
            )
        )
    return points
