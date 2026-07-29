import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useCity } from '../hooks/useCity';
import type { CatalogBrand } from '../types';
import Icon from '../components/Icon';

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
          <Icon name="pin" size={15} />
          {city}
        </button>
      </div>
      <input
        className="search-input"
        type="search"
        placeholder="Сеть, акция или товар…"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
      />

      {brands === null && (
        <div className="skeleton-grid" aria-label="Загружаем сети" aria-busy="true">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div className="skeleton skeleton-tile" key={i} />
          ))}
        </div>
      )}

      {brands !== null && brands.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="search" size={44} strokeWidth={1.4} /></div>
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

      {brands !== null && brands.length > 0 && (
        <div className="brand-grid">
          {brands.map((brand) => (
            <button
              key={brand.id}
              className="brand-tile"
              onClick={() => navigate(`/brand/${brand.id}`)}
            >
              {brand.logo_url ? (
                <img className="brand-tile-logo" src={brand.logo_url} alt="" />
              ) : (
                <span className="brand-tile-avatar" style={{ background: brand.color }}>
                  {brand.name[0]}
                </span>
              )}
              <span className="brand-tile-name">{brand.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
