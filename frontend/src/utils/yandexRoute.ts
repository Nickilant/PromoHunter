export interface RoutePoint {
  lat: number;
  lng: number;
}

function routeQuery(from: RoutePoint, to: RoutePoint): string {
  const points = `${from.lat},${from.lng}~${to.lat},${to.lng}`;
  return `mode=routes&rtext=${encodeURIComponent(points)}&rtt=auto`;
}

/** Официальная iframe-версия Яндекс Карт для просмотра внутри PromoHunter. */
export function yandexRouteWidgetUrl(from: RoutePoint, to: RoutePoint): string {
  return `https://yandex.ru/map-widget/v1/?${routeQuery(from, to)}`;
}
