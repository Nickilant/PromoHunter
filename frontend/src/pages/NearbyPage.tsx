import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import Icon from '../components/Icon';
import RestaurantModal from '../components/RestaurantModal';
import { useCity } from '../hooks/useCity';
import type { RestaurantListItem } from '../types';
import { distanceM, formatDistance } from '../utils/distance';
import { timeAgo } from '../utils/time';

// Показываем ближайшие: дальше человек всё равно не пойдёт, а список
// на весь город есть на карте и во вкладке акций
const LIMIT = 20;

interface Nearby extends RestaurantListItem {
  meters: number;
}

export default function NearbyPage() {
  const { city } = useCity();
  const [restaurants, setRestaurants] = useState<RestaurantListItem[]>([]);
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(true);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

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

  const nearby: Nearby[] = position
    ? restaurants
        .map((r) => ({ ...r, meters: distanceM(position, r) }))
        .sort((a, b) => a.meters - b.meters)
        .slice(0, LIMIT)
    : [];

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Рядом с вами</h1>
        <p className="muted">
          Точки по расстоянию от вас. Загляните в карточку — там акции и
          что в них сейчас есть.
        </p>
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
          <button
            key={r.id}
            className="nearby-item"
            onClick={() => setSelectedId(r.id)}
          >
            <span className="nearby-distance">{formatDistance(r.meters)}</span>
            <span className="nearby-body">
              <span className="nearby-title">
                <span
                  className="brand-chip small"
                  style={{ background: r.brand.color }}
                >
                  {r.brand.name}
                </span>
                {r.title && <span className="nearby-name">{r.title}</span>}
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
        );
      })}

      {selectedId !== null && (
        <RestaurantModal
          restaurantId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
