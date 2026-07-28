import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { MapFocus, RestaurantsMap } from '../components/MapView';
import PromotionAccordion from '../components/PromotionAccordion';
import ReportModal from '../components/ReportModal';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import { geocodeAddress } from '../utils/geocode';
import type {
  PromotionWithStatuses,
  RestaurantDetail,
  RestaurantListItem,
  RestaurantShort,
} from '../types';

export default function MapPage() {
  const [restaurants, setRestaurants] = useState<RestaurantListItem[]>([]);
  const [selected, setSelected] = useState<RestaurantDetail | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [searchPoint, setSearchPoint] = useState<MapFocus | null>(null);
  const [reportTarget, setReportTarget] = useState<{
    restaurant: RestaurantShort;
    promotion: PromotionWithStatuses;
  } | null>(null);
  const { user } = useAuth();
  const { city } = useCity();
  const navigate = useNavigate();

  useEffect(() => {
    if (!city) return;
    api
      .get<RestaurantListItem[]>(`/restaurants?city=${encodeURIComponent(city)}`)
      .then(setRestaurants)
      .catch(() => {});
  }, [city]);

  const select = (id: number) => {
    setSelectedId(id);
    setSelected(null);
    api.get<RestaurantDetail>(`/restaurants/${id}`).then(setSelected).catch(() => {});
  };

  // Поиск адреса: по умолчанию в выбранном городе;
  // другой город можно указать прямо в строке поиска
  const submitSearch = async (e: FormEvent) => {
    e.preventDefault();
    const query = search.trim();
    if (!query || searching) return;
    setSearching(true);
    setSearchError(null);
    const point = await geocodeAddress(query, city);
    setSearching(false);
    if (point) {
      setSearchPoint(point);
      setFocus({ lat: point.lat, lng: point.lng, zoom: 16 });
    } else {
      setSearchError('Адрес не нашёлся — попробуйте уточнить');
    }
  };

  const openReport = (restaurant: RestaurantShort, promotion: PromotionWithStatuses) => {
    if (!user) {
      navigate('/login');
      return;
    }
    setReportTarget({ restaurant, promotion });
  };

  return (
    <div className="map-page">
      <RestaurantsMap
        restaurants={restaurants}
        selectedId={selectedId}
        onSelect={select}
        focus={focus}
        searchPoint={searchPoint}
      />

      <form className="map-search" onSubmit={submitSearch}>
        <input
          className="search-input"
          type="search"
          placeholder={`Адрес в городе ${city ?? ''}…`}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setSearchError(null);
          }}
        />
        <button className="btn btn-primary" disabled={searching} aria-label="Найти">
          {searching ? '…' : '🔍'}
        </button>
      </form>
      {searchError && <div className="map-search-error">{searchError}</div>}

      {selectedId !== null && (
        <div className="bottom-sheet">
          <div className="bottom-sheet-inner">
            <div className="bottom-sheet-grip" />
            <div className="rest-card-head">
              {selected ? (
                <>
                  <span
                    className="brand-chip"
                    style={{ background: selected.brand.color }}
                  >
                    {selected.brand.name}
                  </span>
                  <div className="rest-card-titles">
                    {selected.title && <div className="title">{selected.title}</div>}
                    <div className="address">{selected.address}</div>
                  </div>
                </>
              ) : (
                <div className="rest-card-titles">
                  <div className="address">Загружаем…</div>
                </div>
              )}
              <button
                className="modal-close"
                style={{ marginLeft: 'auto' }}
                onClick={() => {
                  setSelectedId(null);
                  setSelected(null);
                }}
                aria-label="Закрыть"
              >
                ✕
              </button>
            </div>
            {selected && selected.promotions.length === 0 && (
              <div className="empty-state" style={{ padding: '16px 24px 24px' }}>
                Сейчас в этой точке нет действующих акций
              </div>
            )}
            {selected?.promotions.map((promo) => (
              <PromotionAccordion
                key={promo.id}
                restaurant={selected}
                promotion={promo}
                onReport={openReport}
                defaultOpen={selected.promotions.length === 1}
              />
            ))}
          </div>
        </div>
      )}

      {reportTarget && (
        <ReportModal
          restaurant={reportTarget.restaurant}
          promotion={reportTarget.promotion}
          onClose={() => setReportTarget(null)}
          onReported={() => selectedId !== null && select(selectedId)}
        />
      )}
    </div>
  );
}
