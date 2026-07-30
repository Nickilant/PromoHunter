import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { api } from '../api/client';
import { CaptureTimer, OwnerChip } from '../components/GameBits';
import RestaurantModal from '../components/RestaurantModal';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import type { RestaurantListItem } from '../types';
import { timeAgo } from '../utils/time';
import Icon from '../components/Icon';

// Внутри сети: список адресов в выбранном городе.
// Тап по адресу открывает модалку точки с акциями.
export default function BrandPage() {
  const { brandId } = useParams();
  const [restaurants, setRestaurants] = useState<RestaurantListItem[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const { city } = useCity();
  const { enabled: gameEnabled, pointOf } = useGame();
  const navigate = useNavigate();

  useEffect(() => {
    if (!city || !brandId) return;
    const params = new URLSearchParams({ city, brand_id: brandId });
    api
      .get<RestaurantListItem[]>(`/restaurants?${params}`)
      .then(setRestaurants)
      .catch(() => setRestaurants([]));
  }, [city, brandId]);

  const brand = restaurants?.[0]?.brand ?? null;

  return (
    <div className="page">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate(-1)} aria-label="Назад">
          <Icon name="chevronLeft" size={22} />
        </button>
        {brand ? (
          <span className="brand-chip" style={{ background: brand.color }}>
            {brand.name}
          </span>
        ) : (
          <h1>Адреса</h1>
        )}
        <span className="city-chip muted-chip">
          <Icon name="pin" size={15} />
          {city}
        </span>
      </div>

      {restaurants === null && (
        <div className="skeleton-list" aria-label="Загружаем адреса" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div className="skeleton skeleton-row" key={i} />
          ))}
        </div>
      )}

      {restaurants !== null && restaurants.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="city" size={44} strokeWidth={1.4} /></div>
          <div>В городе {city} у этой сети пока нет точек</div>
        </div>
      )}

      {restaurants?.map((r) => {
        const updated = timeAgo(r.last_report_at);
        const point = gameEnabled ? pointOf(r.id) : undefined;
        return (
          <button key={r.id} className="address-card" onClick={() => setOpenId(r.id)}>
            <span className="address-card-body">
              {r.title && <span className="brand-card-title">{r.title}</span>}
              <span className={r.title ? 'brand-card-meta' : 'brand-card-title'}>
                {r.address}
              </span>
              <span className="brand-card-meta">
                {updated ? `отчёты ${updated}` : 'отчётов ещё не было'}
              </span>
              {point && (
                <span className="address-card-game">
                  <OwnerChip owner={point.owner} size="small" />
                  <CaptureTimer point={point} />
                </span>
              )}
            </span>
            <span className="chevron-right"><Icon name="chevronRight" size={20} /></span>
          </button>
        );
      })}

      {openId !== null && (
        <RestaurantModal restaurantId={openId} onClose={() => setOpenId(null)} />
      )}
    </div>
  );
}
