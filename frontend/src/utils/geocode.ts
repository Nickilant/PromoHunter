// Геокодинг адресов через Nominatim (OSM, без ключей).
// Сначала ищем в выбранном городе; если пользователь указал другой город
// прямо в строке — сработает второй запрос без привязки.

export interface GeoPoint {
  lat: number;
  lng: number;
  label: string;
}

/** Город по координатам (обратный геокодинг) — для «определить мой город» */
export async function reverseGeocodeCity(
  lat: number,
  lng: number,
): Promise<string | null> {
  try {
    const resp = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=10&accept-language=ru`,
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const address = data.address ?? {};
    return (
      address.city || address.town || address.village || address.municipality || null
    );
  } catch {
    return null;
  }
}

/** Координаты города (кэшируются в localStorage) — для центрирования карты */
export async function geocodeCity(city: string): Promise<GeoPoint | null> {
  const key = `promohunter_city_geo:${city.toLowerCase()}`;
  const cached = localStorage.getItem(key);
  if (cached) {
    try {
      return JSON.parse(cached) as GeoPoint;
    } catch {
      localStorage.removeItem(key);
    }
  }
  const point = await geocodeAddress(city, null);
  if (point) localStorage.setItem(key, JSON.stringify(point));
  return point;
}

export async function geocodeAddress(
  query: string,
  city: string | null,
): Promise<GeoPoint | null> {
  const attempts =
    city && !query.toLowerCase().includes(city.toLowerCase())
      ? [`${query}, ${city}`, query]
      : [query];

  for (const q of attempts) {
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&accept-language=ru&q=${encodeURIComponent(q)}`,
      );
      if (!resp.ok) continue;
      const data: { lat: string; lon: string; display_name: string }[] =
        await resp.json();
      if (data[0]) {
        return {
          lat: Number(data[0].lat),
          lng: Number(data[0].lon),
          label: data[0].display_name,
        };
      }
    } catch {
      /* сеть недоступна — вернём null */
    }
  }
  return null;
}
