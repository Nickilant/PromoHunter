"""Получение точек OpenStreetMap для ручного административного импорта."""

import math
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


MISSING_ADDRESS = "Адрес не указан в OSM"
SEARCH_TAGS = ("name", "name:ru", "brand", "operator", "official_name", "short_name")


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
    if street and number:
        return f"{street}, {number}"[:300]
    return (tags.get("addr:full") or MISSING_ADDRESS)[:300]


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


def _coordinates(element: dict) -> tuple[float, float] | None:
    center = element.get("center") or element
    lat, lng = center.get("lat"), center.get("lon")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def _distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lng1 = first
    lat2, lng2 = second
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def _is_match(tags: dict[str, str], pattern: str) -> bool:
    return any(re.search(pattern, tags.get(key, ""), flags=re.IGNORECASE) for key in SEARCH_TAGS)


def _points_from_elements(elements: list[dict], query: str) -> list[OsmPoint]:
    pattern = _search_pattern(query)
    address_objects: list[tuple[tuple[float, float], str]] = []
    for element in elements:
        coordinates = _coordinates(element)
        if coordinates is None:
            continue
        address = _address(element.get("tags") or {})
        if address != MISSING_ADDRESS:
            address_objects.append((coordinates, address))

    points: list[OsmPoint] = []
    seen: set[tuple[str, int]] = set()
    for element in elements:
        tags = element.get("tags") or {}
        if not _is_match(tags, pattern):
            continue
        coordinates = _coordinates(element)
        if coordinates is None:
            continue
        source = (str(element.get("type", "node"))[:12], int(element["id"]))
        if source in seen:
            continue
        seen.add(source)
        address = _address(tags)
        if address == MISSING_ADDRESS and address_objects:
            nearest_coordinates, nearest_address = min(
                address_objects, key=lambda candidate: _distance_m(coordinates, candidate[0])
            )
            if _distance_m(coordinates, nearest_coordinates) <= 75:
                address = nearest_address
        points.append(
            OsmPoint(
                osm_type=source[0],
                osm_id=source[1],
                # В PromoHunter название точки по умолчанию совпадает с адресом.
                title=address if address != MISSING_ADDRESS else None,
                address=address,
                lat=coordinates[0],
                lng=coordinates[1],
            )
        )
    return points


def find_restaurants(city: str, query: str) -> list[OsmPoint]:
    south, west, north, east = _city_bbox(city)
    pattern = _search_pattern(query.strip())
    bbox = f"{south},{west},{north},{east}"
    overpass_query = f"""
[out:json][timeout:35];
nwr[~\"^(name|name:ru|brand|operator|official_name|short_name)$\"~\"{pattern}\",i]({bbox})->.matches;
(
  .matches;
  nwr(around.matches:75)[\"addr:housenumber\"];
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

    return _points_from_elements(elements, query)[: settings.osm_import_limit]
