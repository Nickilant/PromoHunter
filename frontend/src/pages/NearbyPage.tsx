import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import Icon from '../components/Icon';
import RestaurantModal from '../components/RestaurantModal';
import RouteBrowserModal from '../components/RouteBrowserModal';
import { useCity } from '../hooks/useCity';
import type { RestaurantListItem } from '../types';
import { distanceM, formatDistance } from '../utils/distance';
import { timeAgo } from '../utils/time';

// Показываем по ближайшей точке каждой сети: полный список адресов всё равно
// доступен на карте и внутри бренда, а здесь важен быстрый выбор, куда идти.
const LIMIT = 20;

interface Nearby extends RestaurantListItem {
  meters: number;
}

function nearestRestaurantPerBrand(
  restaurants: RestaurantListItem[],
  position: { lat: number; lng: number },
): Nearby[] {
  const sorted = restaurants
    .map((restaurant) => ({
      ...restaurant,
      meters: distanceM(position, restaurant),
    }))
    .sort((a, b) => a.meters - b.meters);
  const seenBrands = new Set<number>();
  return sorted
    .filter((restaurant) => {
      if (seenBrands.has(restaurant.brand.id)) return false;
      seenBrands.add(restaurant.brand.id);
      return true;
    })
    .slice(0, LIMIT);
}

export default function NearbyPage() {
  const { city } = useCity();
  const [restaurants, setRestaurants] = useState<RestaurantListItem[]>([]);
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(true);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [routeTarget, setRouteTarget] = useState<RestaurantListItem | null>(null);

  useEffect(() => {
    if (!city) return;
    api
      .get<RestaurantListItem[]>(`/restaurants?city=${encodeURIComponent(city)}`)
      .then(setRestaurants)
      .catch(() => {});
  }, [city]);

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setLocating(false);
      setGeoError('Геолокация недоступна на этом устройстве');
      return;
    }
    setLocating(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      () => {
        setLocating(false);
        setGeoError('Нужен доступ к геолокации — иначе не понять, что рядом');
      },
      { enableHighAccuracy: true, timeout: 12000 },
    );
  }, []);

  useEffect(locate, [locate]);

  const nearby = position ? nearestRestaurantPerBrand(restaurants, position) : [];

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Рядом с вами</h1>
      </div>

      {locating && (
        <div className="skeleton-list" aria-label="Определяем, где вы" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div className="skeleton" style={{ height: 68, borderRadius: 12 }} key={i} />
          ))}
        </div>
      )}

      {!locating && geoError && (
        <div className="empty-state">
          <div className="big">
            <Icon name="locate" size={44} strokeWidth={1.4} />
          </div>
          <div>{geoError}</div>
          <button className="btn btn-primary" onClick={locate}>
            Попробовать снова
          </button>
          <Link to="/map" className="btn btn-ghost">
            Открыть карту
          </Link>
        </div>
      )}

      {!locating && !geoError && nearby.length === 0 && (
        <div className="empty-state">
          <div className="big">
            <Icon name="pin" size={44} strokeWidth={1.4} />
          </div>
          <div>
            В городе {city} точек пока нет. Знаете ресторан поблизости —
            расскажите, добавим.
          </div>
          <Link to="/suggest/restaurant" className="btn btn-primary">
            Добавить ресторан
          </Link>
        </div>
      )}

      {nearby.map((r) => {
        const updated = timeAgo(r.last_report_at);
        return (
          <div className="nearby-card" key={r.id}>
            <button className="nearby-item" onClick={() => setSelectedId(r.id)}>
              <span className="nearby-distance">{formatDistance(r.meters)}</span>
              <span className="nearby-body">
                <span className="nearby-title">
                  <span
                    className="brand-chip small"
                    style={{ background: r.brand.color }}
                  >
                    {r.brand.name}
                  </span>
                </span>
                <span className="nearby-address">{r.address}</span>
                <span className="nearby-meta muted">
                  {r.active_promotions_count > 0
                    ? `акций: ${r.active_promotions_count}`
                    : 'акций нет'}
                  {updated && ` · отчёты ${updated}`}
                </span>
              </span>
              <span className="chevron-right">
                <Icon name="chevronRight" size={20} />
              </span>
            </button>
            <button
              className="nearby-route"
              onClick={() => setRouteTarget(r)}
              aria-label={`Построить маршрут в Яндекс Картах до ${r.brand.name}, ${r.address}`}
            >
              <Icon name="route" size={20} />
              <span>Маршрут</span>
            </button>
          </div>
        );
      })}

      {selectedId !== null && (
        <RestaurantModal
          restaurantId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
      {position && routeTarget && (
        <RouteBrowserModal
          from={position}
          to={routeTarget}
          destination={`${routeTarget.brand.name}, ${routeTarget.address}`}
          onClose={() => setRouteTarget(null)}
        />
      )}
    </div>
  );
}
