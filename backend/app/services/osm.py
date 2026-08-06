"""Получение точек OpenStreetMap для ручного административного импорта."""

import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import product
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
OVERPASS_FALLBACK_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def _client(read_timeout: float = 40.0) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.osm_user_agent, "Accept": "application/json"},
        timeout=httpx.Timeout(read_timeout, connect=10.0),
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


def _search_values(query: str) -> list[str]:
    """Варианты точного написания для быстрого индексного поиска Overpass."""
    words = re.findall(r"\w+", query, flags=re.UNICODE)
    values = {query.strip()}
    if 1 < len(words) <= 4:
        separators = (" ", " - ", " – ", " — ")
        for combination in product(separators, repeat=len(words) - 1):
            values.add("".join(word + (combination[index] if index < len(combination) else "") for index, word in enumerate(words)))
    return sorted(value for value in values if value)


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


def _overpass(query: str, read_timeout: float) -> list[dict]:
    urls = tuple(dict.fromkeys((settings.osm_overpass_url, *OVERPASS_FALLBACK_URLS)))
    deadline = time.monotonic() + read_timeout
    last_error: Exception | None = None
    for index, url in enumerate(urls):
        remaining = deadline - time.monotonic()
        if remaining < 2:
            break
        attempt_timeout = max(2.0, remaining / (len(urls) - index))
        try:
            with _client(attempt_timeout) as client:
                response = client.post(
                    url,
                    content=query.encode(),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
                response.raise_for_status()
                return response.json().get("elements", [])
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise httpx.ReadTimeout("Истёк общий таймаут запроса Overpass")


def _split_bbox(bbox: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    middle_lat = (south + north) / 2
    middle_lng = (west + east) / 2
    return [
        (south, west, middle_lat, middle_lng),
        (south, middle_lng, middle_lat, east),
        (middle_lat, west, north, middle_lng),
        (middle_lat, middle_lng, north, east),
    ]


def _search_bbox(
    bbox: tuple[float, float, float, float],
    pattern: str,
    values: list[str],
    deadline: float,
    depth: int = 0,
    exact_search: bool = False,
) -> list[dict]:
    remaining = deadline - time.monotonic()
    if remaining < 3:
        raise httpx.ReadTimeout("Истёк общий таймаут поиска по городу")
    south, west, north, east = bbox
    if exact_search:
        statements = []
        for key in SEARCH_TAGS:
            for value in values:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                statements.append(f'nwr["{key}"="{escaped}"]({south},{west},{north},{east});')
        selector = "(\n" + "\n".join(statements) + "\n);"
    else:
        selector = (
            f'nwr[~"^(name|name:ru|brand|operator|official_name|short_name)$"~"{pattern}",i]'
            f'({south},{west},{north},{east});'
        )
    overpass_query = f"""
[out:json][timeout:{max(2, min(12, int(remaining) - 1))}];
{selector}
out center tags;
"""
    try:
        elements = _overpass(overpass_query, min(14.0, remaining))
        return [item for item in elements if _is_match(item.get("tags") or {}, pattern)]
    except (httpx.HTTPError, ValueError):
        if depth >= 1 or deadline - time.monotonic() < 8:
            raise
        result: list[dict] = []
        for tile in _split_bbox(bbox):
            result.extend(_search_bbox(tile, pattern, values, deadline, depth + 1, exact_search))
        return result


def _unique_elements(elements: list[dict]) -> list[dict]:
    unique: dict[tuple[str, int], dict] = {}
    for element in elements:
        if "id" in element:
            unique[(str(element.get("type", "node")), int(element["id"]))] = element
    return list(unique.values())


def _id_selector(elements: list[dict]) -> str:
    by_type: dict[str, list[str]] = {"node": [], "way": [], "relation": []}
    for element in elements:
        osm_type = str(element.get("type", ""))
        if osm_type in by_type:
            by_type[osm_type].append(str(int(element["id"])))
    return "\n".join(
        f"  {osm_type}(id:{','.join(ids)});"
        for osm_type, ids in by_type.items()
        if ids
    )


def _enrich_addresses(elements: list[dict], query: str) -> list[OsmPoint]:
    """Догрузить адресное окружение небольшими запросами.

    Ошибка или очередь Overpass в одной пачке не отменяет весь импорт. Общий
    бюджет не даёт синхронному API упереться в минутный таймаут reverse proxy.
    """
    result: list[OsmPoint] = []
    deadline = time.monotonic() + 15.0
    chunk_size = 100
    for start in range(0, len(elements), chunk_size):
        chunk = elements[start : start + chunk_size]
        remaining = deadline - time.monotonic()
        if remaining < 2:
            result.extend(_points_from_elements(chunk, query))
            continue
        selector = _id_selector(chunk)
        overpass_query = f"""
[out:json][timeout:12];
(
{selector}
)->.matches;
(
  .matches;
  nwr(around.matches:75)[\"addr:housenumber\"];
);
out center tags;
"""
        try:
            enriched = _overpass(overpass_query, min(12.0, remaining))
        except (httpx.HTTPError, ValueError):
            enriched = chunk
        result.extend(_points_from_elements(enriched, query))
    return result


def find_restaurants(city: str, query: str) -> list[OsmPoint]:
    bbox = _city_bbox(city)
    normalized_query = query.strip()
    pattern = _search_pattern(normalized_query)
    values = _search_values(normalized_query)
    try:
        south, west, north, east = bbox
        # Запросы по административной границе мегаполиса часто застревают в
        # очереди Overpass. Сразу делим крупные области, а неудачный сектор
        # при необходимости дробим ещё раз.
        is_large = max(north - south, east - west) > 0.35
        initial_boxes = _split_bbox(bbox) if is_large else [bbox]
        deadline = time.monotonic() + 35.0
        if len(initial_boxes) == 1:
            elements = _search_bbox(initial_boxes[0], pattern, values, deadline)
        else:
            # Не более двух одновременных запросов: публичные Overpass-инстансы
            # ограничивают слишком агрессивных клиентов.
            with ThreadPoolExecutor(max_workers=2) as executor:
                batches = list(
                    executor.map(
                        lambda initial_bbox: _search_bbox(
                            initial_bbox, pattern, values, deadline, exact_search=True
                        ),
                        initial_boxes,
                    )
                )
            elements = [element for batch in batches for element in batch]
    except (httpx.HTTPError, ValueError) as error:
        raise OsmError("OpenStreetMap сейчас не ответил - попробуйте немного позже") from error

    elements = _unique_elements(elements)[: settings.osm_import_limit]
    return _enrich_addresses(elements, query)
