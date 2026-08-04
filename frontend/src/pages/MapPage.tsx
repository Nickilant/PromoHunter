import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { api } from '../api/client';
import CapturePanel from '../components/CapturePanel';
import BrandFilterModal from '../components/BrandFilterModal';
import DataIssueModal from '../components/DataIssueModal';
import { MapFocus, RestaurantsMap } from '../components/MapView';
import PromotionAccordion from '../components/PromotionAccordion';
import PromoCodesModal from '../components/PromoCodesModal';
import ReportModal from '../components/ReportModal';
import RestaurantHistoryModal from '../components/RestaurantHistoryModal';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import { useSubscriptions } from '../hooks/useSubscriptions';
import { geocodeAddress, geocodeCity } from '../utils/geocode';
import type {
  Brand,
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
  const [filterOpen, setFilterOpen] = useState(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [codesOpen, setCodesOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [brandLogoUrl, setBrandLogoUrl] = useState<string | null>(null);
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<number>>(() => new Set());
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
  const brands = useMemo(
    () => Array.from(new Map(restaurants.map((restaurant) => [restaurant.brand.id, restaurant.brand])).values())
      .sort((a, b) => a.name.localeCompare(b.name, 'ru')),
    [restaurants],
  );
  const visibleRestaurants = useMemo(
    () => selectedBrandIds.size === 0
      ? restaurants
      : restaurants.filter((restaurant) => selectedBrandIds.has(restaurant.brand.id)),
    [restaurants, selectedBrandIds],
  );

  useEffect(() => {
    if (!selected) {
      setBrandLogoUrl(null);
      return;
    }
    if (selected.brand.logo_url) {
      setBrandLogoUrl(selected.brand.logo_url);
      return;
    }

    let cancelled = false;
    api.get<Brand[]>('/brands').then((items) => {
      if (cancelled) return;
      setBrandLogoUrl(
        items.find((brand) => brand.id === selected.brand.id)?.logo_url ?? null,
      );
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selected]);

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
    setSelectedBrandIds(new Set());
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
        restaurants={visibleRestaurants}
        keepFocus={focusedFromUrl.current}
        selectedId={selectedId}
        onSelect={select}
        focus={focus}
        searchPoint={searchPoint}
        points={gameEnabled ? points : undefined}
        layerVisible={layerVisible}
        onToggleLayer={toggleLayer}
        selectedBrandCount={selectedBrandIds.size}
        onOpenBrandFilter={() => setFilterOpen(true)}
      />

      {filterOpen && (
        <BrandFilterModal
          brands={brands}
          selectedIds={selectedBrandIds}
          onApply={(ids) => {
            setSelectedBrandIds(new Set(ids));
            if (selectedId !== null && ids.size > 0) {
              const current = restaurants.find((restaurant) => restaurant.id === selectedId);
              if (current && !ids.has(current.brand.id)) {
                setSelectedId(null);
                setSelected(null);
              }
            }
          }}
          onClose={() => setFilterOpen(false)}
        />
      )}

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
            <div className="rest-card-head restaurant-modal-head map-point-head">
              {selected ? (
                <div className="restaurant-modal-identity">
                  {brandLogoUrl ? (
                    <img
                      className="restaurant-modal-logo"
                      src={brandLogoUrl}
                      alt={selected.brand.name}
                    />
                  ) : (
                    <span
                      className="brand-chip"
                      style={{ background: selected.brand.color }}
                    >
                      {selected.brand.name}
                    </span>
                  )}
                  <div className="restaurant-modal-location">
                    <div className="restaurant-modal-address">{selected.address}</div>
                    {selected.title && (
                      <div className="restaurant-modal-title">{selected.title}</div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="restaurant-modal-identity">
                  <span
                    className="skeleton on-surface restaurant-modal-logo-skeleton"
                  />
                  <span
                    className="skeleton on-surface restaurant-modal-address-skeleton"
                  />
                </div>
              )}
              <button
                className="modal-close"
                onClick={() => {
                  setSelectedId(null);
                  setSelected(null);
                }}
                aria-label="Закрыть"
              >
                <Icon name="close" size={20} />
              </button>
              {selected && selectedId !== null && (
                <div className="restaurant-modal-actions">
                  <a
                    href={`https://yandex.ru/maps/?mode=routes&rtext=~${selected.lat},${selected.lng}&rtt=auto`}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Построить маршрут до ${selected.address}`}
                  >
                    <Icon name="route" size={18} />
                    <span>Построить маршрут</span>
                  </a>
                  <button onClick={() => setHistoryOpen(true)}>
                    <Icon name="chart" size={18} />
                    <span>Сводка</span>
                  </button>
                  <button onClick={() => setCodesOpen(true)}>
                    <Icon name="ticket" size={18} />
                    <span>Промокоды</span>
                  </button>
                  <button
                    className={isSubscribedToRestaurant(selectedId) ? 'on' : ''}
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
                  >
                    <Icon
                      name={isSubscribedToRestaurant(selectedId) ? 'bell' : 'bellOff'}
                      size={18}
                    />
                    <span>
                      {isSubscribedToRestaurant(selectedId) ? 'Подписан' : 'Подписаться'}
                    </span>
                  </button>
                </div>
              )}
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
              {selected && <button className="data-issue-link data-issue-link-bottom" onClick={() => {
                if (!user) { navigate('/login'); return; }
                setIssueOpen(true);
              }}><Icon name="alert" size={16} />Сообщить об ошибке в данных</button>}
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
      {issueOpen && selected && <DataIssueModal restaurant={selected} onClose={() => setIssueOpen(false)} />}
      {codesOpen && selected && (
        <PromoCodesModal brand={selected.brand} onClose={() => setCodesOpen(false)} />
      )}
      {historyOpen && selected && (
        <RestaurantHistoryModal
          restaurant={selected}
          onClose={() => setHistoryOpen(false)}
        />
      )}
    </div>
  );
}
