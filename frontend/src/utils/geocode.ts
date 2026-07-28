// Геокодинг адресов через Nominatim (OSM, без ключей).
// Сначала ищем в выбранном городе; если пользователь указал другой город
// прямо в строке — сработает второй запрос без привязки.

export interface GeoPoint {
  lat: number;
  lng: number;
  label: string;
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
