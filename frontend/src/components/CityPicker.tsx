import { useEffect, useState } from 'react';

import { api } from '../api/client';
import type { CityInfo } from '../types';

interface Props {
  current: string | null;
  onSelect: (city: string) => void;
  /** undefined — выбор обязателен (первый вход), закрыть нельзя */
  onClose?: () => void;
}

export default function CityPicker({ current, onSelect, onClose }: Props) {
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  const trimmed = query.trim();
  const filtered = cities.filter((c) =>
    c.name.toLowerCase().includes(trimmed.toLowerCase()),
  );
  const exactMatch = cities.some(
    (c) => c.name.toLowerCase() === trimmed.toLowerCase(),
  );

  return (
    <div className="city-picker">
      <div className="city-picker-inner">
        <div className="city-picker-head">
          <div>
            <h1>Ваш город</h1>
            <div className="subtitle">Покажем акции и рестораны рядом</div>
          </div>
          {onClose && (
            <button className="modal-close" onClick={onClose} aria-label="Закрыть">
              ✕
            </button>
          )}
        </div>
        <input
          className="search-input"
          type="search"
          placeholder="Найти город…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <div className="city-list">
          {filtered.map((c) => (
            <button
              key={c.name}
              className={`city-item ${current === c.name ? 'current' : ''}`}
              onClick={() => onSelect(c.name)}
            >
              <span>{c.name}</span>
              <span className="muted">
                {c.restaurants_count}{' '}
                {c.restaurants_count === 1 ? 'точка' : 'точек'}
              </span>
            </button>
          ))}
          {trimmed && !exactMatch && (
            <button className="city-item other" onClick={() => onSelect(trimmed)}>
              <span>Выбрать «{trimmed}»</span>
              <span className="muted">точек пока нет</span>
            </button>
          )}
          {!trimmed && filtered.length === 0 && (
            <div className="empty-state">Загружаем города…</div>
          )}
        </div>
      </div>
    </div>
  );
}
