import { FormEvent, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { api } from '../api/client';
import CapturePanel from '../components/CapturePanel';
import { MapFocus, RestaurantsMap } from '../components/MapView';
import PromotionAccordion from '../components/PromotionAccordion';
import ReportModal from '../components/ReportModal';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import { useSubscriptions } from '../hooks/useSubscriptions';
import { geocodeAddress, geocodeCity } from '../utils/geocode';
import type {
  PromotionWithStatuses,
  RestaurantDetail,
  RestaurantListItem,
  RestaurantShort,
} from '../types';
import Icon from '../components/Icon';

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
  const { isSubscribedToRestaurant, toggleRestaurant } = useSubscriptions();
  const { enabled: gameEnabled, points, layerVisible, toggleLayer } = useGame();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  // ?point=<id> — карту открыли из карточки точки кнопкой «На карте»
  const requestedPoint = params.get('point');
  const focusedFromUrl = useRef(false);

  useEffect(() => {
    if (!requestedPoint || focusedFromUrl.current) return;
    const id = Number(requestedPoint);
    if (!Number.isFinite(id)) return;
    focusedFromUrl.current = true;
    api
      .get<RestaurantDetail>(`/restaurants/${id}`)
      .then((detail) => {
        setSelectedId(detail.id);
        setSelected(detail);
        setFocus({ lat: detail.lat, lng: detail.lng, zoom: 16 });
      })
      .catch(() => {})
      // Параметр одноразовый: иначе возврат на вкладку снова открывал бы точку
      .finally(() => setParams({}, { replace: true }));
  }, [requestedPoint, setParams]);

  useEffect(() => {
    if (!city) return;
    let cancelled = false;
    api
      .get<RestaurantListItem[]>(`/restaurants?city=${encodeURIComponent(city)}`)
      .then((list) => {
        if (cancelled) return;
        setRestaurants(list);
        // Точек нет — карта не впишет маркеры, центрируем на самом городе
        if (list.length === 0) {
          geocodeCity(city).then((point) => {
            if (point && !cancelled) {
              setFocus({ lat: point.lat, lng: point.lng, zoom: 11 });
            }
          });
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
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
        keepFocus={focusedFromUrl.current}
        selectedId={selectedId}
        onSelect={select}
        focus={focus}
        searchPoint={searchPoint}
        points={gameEnabled ? points : undefined}
        layerVisible={layerVisible}
        onToggleLayer={toggleLayer}
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
          {searching ? <span className="spinner" /> : <Icon name="search" size={18} />}
        </button>
      </form>
      {searchError && <div className="map-search-error">{searchError}</div>}

      {selectedId !== null && (
        <div className="bottom-sheet">
          <div className="bottom-sheet-inner" key={selectedId}>
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
                <>
                  <span
                    className="skeleton on-surface"
                    style={{ width: 96, height: 24, borderRadius: 999 }}
                  />
                  <span
                    className="skeleton on-surface"
                    style={{ width: '45%', height: 16, borderRadius: 8 }}
                  />
                </>
              )}
              {/* Колокольчик — в одной строке с названием: отдельной строкой
                  он налезал на состояние точки */}
              {selected && selectedId !== null && (
                <button
                  className={`head-bell${
                    isSubscribedToRestaurant(selectedId) ? ' on' : ''
                  }`}
                  style={{ marginLeft: 'auto' }}
                  onClick={() => {
                    if (!user) {
                      navigate('/login');
                      return;
                    }
                    toggleRestaurant(selectedId);
                  }}
                  aria-pressed={isSubscribedToRestaurant(selectedId)}
                  aria-label={
                    isSubscribedToRestaurant(selectedId)
                      ? 'Отписаться от новостей точки'
                      : 'Подписаться на новости точки'
                  }
                  title={
                    isSubscribedToRestaurant(selectedId)
                      ? 'Отписаться от новостей точки'
                      : 'Подписаться на новости точки'
                  }
                >
                  <Icon
                    name={isSubscribedToRestaurant(selectedId) ? 'bell' : 'bellOff'}
                    size={19}
                  />
                </button>
              )}
              <button
                className="modal-close"
                style={selected ? undefined : { marginLeft: 'auto' }}
                onClick={() => {
                  setSelectedId(null);
                  setSelected(null);
                }}
                aria-label="Закрыть"
              >
                <Icon name="close" size={20} />
              </button>
            </div>
            {selectedId !== null && <CapturePanel restaurantId={selectedId} />}
            {/* скроллится только список акций — шапка и подписка закреплены */}
            <div className="bottom-sheet-scroll">
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
