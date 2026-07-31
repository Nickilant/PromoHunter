const EARTH_RADIUS_M = 6371000;

/** Расстояние по большому кругу, метры. */
export function distanceM(
  from: { lat: number; lng: number },
  to: { lat: number; lng: number },
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(to.lat - from.lat);
  const dLng = toRad(to.lng - from.lng);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(from.lat)) * Math.cos(toRad(to.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
}

/** «250 м» / «1,4 км» — точность выше метров человеку не нужна. */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters / 10) * 10} м`;
  const km = meters / 1000;
  return `${km < 10 ? km.toFixed(1).replace('.', ',') : Math.round(km)} км`;
}
