import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useCity } from '../hooks/useCity';
import type { CatalogBrand } from '../types';

// Главный экран: сети-категории выбранного города.
// Тап по сети -> список её адресов -> модалка точки с акциями.
export default function FeedPage() {
  const [query, setQuery] = useState('');
  const [brands, setBrands] = useState<CatalogBrand[] | null>(null);
  const debounce = useRef<number | undefined>(undefined);
  const { city, openPicker } = useCity();
  const navigate = useNavigate();

  const load = useCallback(
    (q: string) => {
      if (!city) return;
      const params = new URLSearchParams({ city });
      if (q.trim()) params.set('q', q.trim());
      api
        .get<CatalogBrand[]>(`/catalog?${params}`)
        .then(setBrands)
        .catch(() => setBrands([]));
    },
    [city],
  );

  useEffect(() => {
    setBrands(null);
    load(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city]);

  const onQueryChange = (value: string) => {
    setQuery(value);
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => load(value), 300);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Акции</h1>
        <button className="city-chip" onClick={openPicker}>
          📍 {city}
        </button>
      </div>
      <input
        className="search-input"
        type="search"
        placeholder="Сеть, акция или товар…"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
      />

      {brands === null && <div className="empty-state">Загружаем…</div>}

      {brands !== null && brands.length === 0 && (
        <div className="empty-state">
          <div className="big">🔍</div>
          <div>
            {query.trim()
              ? 'Ничего не нашлось. Попробуйте другой запрос — или заявите акцию сами.'
              : `В городе ${city} пока нет действующих акций. Видели что-то интересное? Расскажите!`}
          </div>
          <Link to="/suggest" className="btn btn-accent">
            Заявить акцию
          </Link>
        </div>
      )}

      {brands?.map((brand) => (
        <button
          key={brand.id}
          className="brand-card"
          onClick={() => navigate(`/brand/${brand.id}`)}
        >
          <span className="brand-avatar" style={{ background: brand.color }}>
            {brand.name[0]}
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">{brand.name}</span>
            <span className="brand-card-meta">
              {brand.restaurants_count}{' '}
              {brand.restaurants_count === 1 ? 'адрес' : 'адресов'} ·{' '}
              {brand.promotions.length}{' '}
              {brand.promotions.length === 1 ? 'акция' : 'акции'}
            </span>
            <span className="brand-card-promos">
              {brand.promotions
                .slice(0, 2)
                .map((p) => p.title)
                .join(' · ')}
              {brand.promotions.length > 2 && ' · …'}
            </span>
          </span>
          <span className="chevron-right">›</span>
        </button>
      ))}
    </div>
  );
}
