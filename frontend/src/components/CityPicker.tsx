import { useEffect, useRef, useState } from 'react';

import { api } from '../api/client';
import type { CityInfo } from '../types';
import { reverseGeocodeCity } from '../utils/geocode';
import Icon from './Icon';
import { useDismiss } from '../hooks/useDismiss';

interface Props {
  current: string | null;
  onSelect: (city: string) => void;
  /** undefined — выбор обязателен (первый вход), закрыть нельзя */
  onClose?: () => void;
}

// Список городов длинный, а нужен почти всегда один из крупных: показываем
// десятку по числу точек, остальное достаётся поиском
const TOP = 10;

export default function CityPicker({ current, onSelect, onClose }: Props) {
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [query, setQuery] = useState('');
  const [detected, setDetected] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const tried = useRef(false);

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  // Координаты уходят напрямую в геокодер OSM, на наш сервер — только город
  const detect = (auto = false) => {
    if (!navigator.geolocation) {
      if (!auto) setGeoError('Геолокация недоступна — выберите город вручную');
      return;
    }
    setGeoError(null);
    // Автоматическая попытка идёт молча: показывать «Определяем…» вместо
    // кнопки, пока человек ничего не просил, — только мешать
    if (!auto) setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const name = await reverseGeocodeCity(
          pos.coords.latitude,
          pos.coords.longitude,
        );
        setDetecting(false);
        if (!name) {
          if (!auto) setGeoError('Не получилось определить город — выберите вручную');
          return;
        }
        setDetected(name);
      },
      () => {
        setDetecting(false);
        if (!auto) setGeoError('Нет доступа к геолокации — выберите город вручную');
      },
      { timeout: 10000 },
    );
  };

  // Пробуем определить город сразу: если разрешение уже дано, человек увидит
  // свой город первой строкой и просто ткнёт в него
  useEffect(() => {
    if (tried.current) return;
    tried.current = true;
    if (!navigator.permissions?.query) return;
    navigator.permissions
      .query({ name: 'geolocation' as PermissionName })
      .then((status) => {
        if (status.state === 'granted') detect(true);
      })
      .catch(() => {});
    // detect стабилен по смыслу: он читает только setState
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trimmed = query.trim();
  const lower = trimmed.toLowerCase();
  const known = (name: string) =>
    cities.find((c) => c.name.toLowerCase() === name.toLowerCase());

  // Определённый город идёт первым и не дублируется в списке ниже
  const detectedName = detected ? (known(detected)?.name ?? detected) : null;
  const rest = cities.filter((c) => c.name !== detectedName);
  const filtered = trimmed
    ? rest.filter((c) => c.name.toLowerCase().includes(lower))
    : rest.slice(0, TOP);
  const exactMatch =
    cities.some((c) => c.name.toLowerCase() === lower) ||
    detectedName?.toLowerCase() === lower;
  const hidden = trimmed ? 0 : Math.max(0, rest.length - TOP);

  return (
    <div
      className={`city-picker${closing ? ' closing' : ''}`}
      onAnimationEnd={onAnimationEnd}
    >
      <div className="city-picker-inner">
        <div className="city-picker-head">
          <div>
            <h1>Ваш город</h1>
            <div className="subtitle">Покажем акции и рестораны рядом</div>
          </div>
          {onClose && (
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          )}
        </div>

        <input
          className="search-input"
          type="search"
          placeholder="Найти город…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div className="city-list">
          {/* Автоопределённый город — всегда первой строкой */}
          {detectedName && !trimmed && (
            <button
              className={`city-item detected ${current === detectedName ? 'current' : ''}`}
              onClick={() => onSelect(detectedName)}
            >
              <span>
                <Icon name="locate" size={15} />
                {detectedName}
              </span>
              <span className="muted">рядом с вами</span>
            </button>
          )}
          {!detectedName && !trimmed && (
            <button
              className={`city-item detect${detecting ? ' is-busy' : ''}`}
              onClick={() => detect()}
              disabled={detecting}
            >
              <span>
                {detecting ? <span className="spinner" /> : <Icon name="locate" size={15} />}
                {detecting ? 'Определяем…' : 'Определить мой город'}
              </span>
            </button>
          )}
          {geoError && <div className="form-error">{geoError}</div>}

          {filtered.map((c) => (
            <button
              key={c.name}
              className={`city-item ${current === c.name ? 'current' : ''}`}
              onClick={() => onSelect(c.name)}
            >
              <span>{c.name}</span>
              <span className="muted">
                {c.restaurants_count === 0
                  ? 'точек пока нет'
                  : `${c.restaurants_count} ${
                      c.restaurants_count === 1 ? 'точка' : 'точек'
                    }`}
              </span>
            </button>
          ))}

          {hidden > 0 && (
            <div className="city-more muted">
              И ещё {hidden} — найдите свой поиском
            </div>
          )}
          {trimmed && !exactMatch && (
            <button className="city-item other" onClick={() => onSelect(trimmed)}>
              <span>Выбрать «{trimmed}»</span>
              <span className="muted">такого города у нас пока нет</span>
            </button>
          )}
          {!trimmed && cities.length === 0 && (
            <div className="skeleton-list" aria-label="Загружаем города" aria-busy="true">
              {[0, 1, 2].map((i) => (
                <div
                  className="skeleton"
                  style={{ height: 52, borderRadius: 12 }}
                  key={i}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
