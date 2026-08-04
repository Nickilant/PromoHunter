import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { api } from '../api/client';
import { CaptureTimer, OwnerChip } from '../components/GameBits';
import FilterSelectModal, { FilterSelectOption } from '../components/FilterSelectModal';
import RestaurantModal from '../components/RestaurantModal';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import type { FeedEntry, ItemStatus } from '../types';
import { timeAgo } from '../utils/time';
import Icon from '../components/Icon';

const STATUS_FILTERS: { value: ItemStatus; label: string }[] = [
  { value: 'available', label: 'Есть' },
  { value: 'unavailable', label: 'Кончилось' },
  { value: 'maybe_gone', label: 'Возможно кончилось' },
  { value: 'maybe_appeared', label: 'Возможно появилось' },
  { value: 'disputed', label: 'Спорно' },
  { value: 'unknown', label: 'Нет данных' },
];

// Внутри сети: список адресов в выбранном городе.
// Тап по адресу открывает модалку точки с акциями.
export default function BrandPage() {
  const { brandId } = useParams();
  const [entries, setEntries] = useState<FeedEntry[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [promotionId, setPromotionId] = useState('');
  const [itemStatus, setItemStatus] = useState<ItemStatus | ''>('');
  const [filterPicker, setFilterPicker] = useState<'promotion' | 'status' | null>(null);
  const { city } = useCity();
  const { enabled: gameEnabled, pointOf } = useGame();
  const navigate = useNavigate();

  useEffect(() => {
    if (!city || !brandId) return;
    const params = new URLSearchParams({ city, brand_id: brandId });
    api
      .get<FeedEntry[]>(`/feed?${params}`)
      .then(setEntries)
      .catch(() => setEntries([]));
  }, [city, brandId]);

  const brand = entries?.[0]?.restaurant.brand ?? null;
  const promotions = Array.from(
    new Map((entries ?? []).flatMap((entry) => entry.promotions).map((promo) => [promo.id, promo])).values(),
  );

  // У крупных сетей в городе десятки адресов — глазами не найти
  const q = query.trim().toLowerCase();
  const shown = (entries ?? []).filter(({ restaurant, promotions: restaurantPromos }) => {
    const addressMatches = !q || restaurant.address.toLowerCase().includes(q) ||
      (restaurant.title ?? '').toLowerCase().includes(q);
    const promoMatches = !promotionId || restaurantPromos.some((promo) => promo.id === Number(promotionId));
    const statusMatches = !itemStatus || restaurantPromos.some((promo) =>
      (!promotionId || promo.id === Number(promotionId)) && promo.items.some((item) => item.status === itemStatus),
    );
    return addressMatches && promoMatches && statusMatches;
  });
  // Строку поиска показываем, когда искать есть в чём
  const searchable = (entries?.length ?? 0) > 5;
  const filtering = Boolean(query.trim() || promotionId || itemStatus);
  const activeFilters = Number(Boolean(promotionId)) + Number(Boolean(itemStatus));
  const promotionOptions: FilterSelectOption[] = [
    { value: '', label: 'Все акции' },
    ...promotions.map((promo) => ({ value: String(promo.id), label: promo.title })),
  ];
  const statusOptions: FilterSelectOption[] = [
    { value: '', label: 'Любой статус', tone: 'any' },
    ...STATUS_FILTERS.map((status) => ({ ...status, tone: status.value })),
  ];
  const selectedPromotionLabel = promotionOptions.find((option) => option.value === promotionId)?.label ?? 'Все акции';
  const selectedStatusLabel = statusOptions.find((option) => option.value === itemStatus)?.label ?? 'Любой статус';

  const resetStructuredFilters = () => {
    setPromotionId('');
    setItemStatus('');
  };

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

      {entries === null && (
        <div className="skeleton-list" aria-label="Загружаем адреса" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div className="skeleton skeleton-row" key={i} />
          ))}
        </div>
      )}

      {searchable && (
        <input
          className="search-input"
          type="search"
          value={query}
          placeholder="Адрес или название точки"
          onChange={(e) => setQuery(e.target.value)}
        />
      )}

      {entries !== null && entries.length > 0 && (
        <div className={`brand-list-filters${activeFilters ? ' active' : ''}`}>
          <div className="brand-filter-heading">
            <span><Icon name="filter" size={17} /><strong>Фильтры</strong>{activeFilters > 0 && <b>{activeFilters}</b>}</span>
            {activeFilters > 0 && <button onClick={resetStructuredFilters}>Сбросить</button>}
          </div>

          <div className="brand-filter-fields">
            <div className={`brand-filter-field${promotionId ? ' selected' : ''}`}>
              <span className="brand-filter-field-label">Акция</span>
              <button className="brand-filter-select" onClick={() => setFilterPicker('promotion')} aria-haspopup="dialog">
                <Icon name="tag" size={17} />
                <span>{selectedPromotionLabel}</span>
                <Icon name="chevronDown" size={17} />
              </button>
            </div>

            <div className={`brand-filter-field${itemStatus ? ' selected' : ''}`}>
              <span className="brand-filter-field-label">Статус наличия</span>
              <button className="brand-filter-select" onClick={() => setFilterPicker('status')} aria-haspopup="dialog">
                <span className={`filter-status-dot ${itemStatus || 'any'}`} />
                <span>{selectedStatusLabel}</span>
                <Icon name="chevronDown" size={17} />
              </button>
            </div>
          </div>
        </div>
      )}

      {entries !== null && entries.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="city" size={44} strokeWidth={1.4} /></div>
          <div>В городе {city} у этой сети пока нет точек</div>
        </div>
      )}

      {entries !== null && entries.length > 0 && shown.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="search" size={44} strokeWidth={1.4} /></div>
          <div>{filtering ? 'Нет точек, подходящих под выбранные фильтры' : 'Ничего не нашлось'}</div>
          <button className="btn btn-ghost" onClick={() => { setQuery(''); setPromotionId(''); setItemStatus(''); }}>
            Сбросить фильтры
          </button>
        </div>
      )}

      {shown.map(({ restaurant: r, promotions: restaurantPromos }) => {
        const lastReportAt = restaurantPromos
          .flatMap((promo) => promo.items)
          .map((item) => item.last_report_at)
          .filter((value): value is string => Boolean(value))
          .sort()
          .slice(-1)[0] ?? null;
        const updated = timeAgo(lastReportAt);
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
              {(promotionId || itemStatus) && (
                <span className="address-filter-match">
                  {restaurantPromos
                    .filter((promo) => (!promotionId || promo.id === Number(promotionId)) && (!itemStatus || promo.items.some((item) => item.status === itemStatus)))
                    .map((promo) => promo.title)
                    .join(' · ')}
                </span>
              )}
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

      {filterPicker === 'promotion' && (
        <FilterSelectModal
          title="Выберите акцию"
          subtitle={`${promotions.length} доступно у этой сети`}
          icon="tag"
          options={promotionOptions}
          value={promotionId}
          onChange={setPromotionId}
          onClose={() => setFilterPicker(null)}
        />
      )}
      {filterPicker === 'status' && (
        <FilterSelectModal
          title="Выберите статус"
          subtitle="Покажем точки с таким состоянием товара"
          icon="question"
          options={statusOptions}
          value={itemStatus}
          onChange={(value) => setItemStatus(value as ItemStatus | '')}
          onClose={() => setFilterPicker(null)}
        />
      )}
    </div>
  );
}
