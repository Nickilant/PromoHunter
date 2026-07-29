import { useEffect, useState } from 'react';

import { api } from '../api/client';
import type { CityInfo } from '../types';
import { reverseGeocodeCity } from '../utils/geocode';
import Icon from './Icon';

interface Props {
  current: string | null;
  onSelect: (city: string) => void;
  /** undefined — выбор обязателен (первый вход), закрыть нельзя */
  onClose?: () => void;
}

export default function CityPicker({ current, onSelect, onClose }: Props) {
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [query, setQuery] = useState('');
  const [detecting, setDetecting] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  // Координаты уходят напрямую в геокодер OSM, на наш сервер — только город
  const detect = () => {
    if (!navigator.geolocation) {
      setGeoError('Геолокация недоступна — выберите город вручную');
      return;
    }
    setGeoError(null);
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const name = await reverseGeocodeCity(
          pos.coords.latitude,
          pos.coords.longitude,
        );
        setDetecting(false);
        if (!name) {
          setGeoError('Не получилось определить город — выберите вручную');
          return;
        }
        const known = cities.find(
          (c) => c.name.toLowerCase() === name.toLowerCase(),
        );
        onSelect(known ? known.name : name);
      },
      () => {
        setDetecting(false);
        setGeoError('Нет доступа к геолокации — выберите город вручную');
      },
      { timeout: 10000 },
    );
  };

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
              <Icon name="close" size={20} />
            </button>
          )}
        </div>
        <button
          className="btn btn-primary btn-block"
          onClick={detect}
          disabled={detecting}
        >
          <Icon name="pin" size={18} />
          {detecting ? 'Определяем…' : 'Определить мой город'}
        </button>
        {geoError && <div className="form-error">{geoError}</div>}
        <input
          className="search-input"
          type="search"
          placeholder="Или найдите вручную…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
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
