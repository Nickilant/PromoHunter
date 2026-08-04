import { useEffect, useState } from 'react';

import { api } from '../api/client';
import Icon from '../components/Icon';
import type { CityInfo, PromotionCityMode, PromotionScope } from '../types';

interface Props {
  value: PromotionScope;
  onChange: (scope: PromotionScope) => void;
  disabled?: boolean;
}

/**
 * Охват акции по городам.
 *
 * Смысл списка задаёт режим: «везде, кроме» (пустой список = вся страна)
 * или «только в». Первый вариант и решает главную задачу — объявить акцию
 * федеральной и выключить её в паре городов, не перечисляя все остальные.
 */
export default function PromotionScopeEditor({ value, onChange, disabled }: Props) {
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  const setMode = (mode: PromotionCityMode) => onChange({ ...value, mode });

  const toggle = (city: string) => {
    const listed = value.cities.some((c) => same(c, city));
    onChange({
      ...value,
      cities: listed
        ? value.cities.filter((c) => !same(c, city))
        : [...value.cities, city],
    });
  };

  const normalizedQuery = query.trim().toLocaleLowerCase('ru');
  const matches = normalizedQuery
    ? cities
        .filter((city) => city.name.toLocaleLowerCase('ru').includes(normalizedQuery))
        .filter((city) => !value.cities.some((selected) => same(selected, city.name)))
        .slice(0, 8)
    : [];

  return (
    <div className="scope-editor">
      <div className="scope-modes">
        <label className={value.mode === 'exclude' ? 'on' : ''}>
          <input
            type="radio"
            checked={value.mode === 'exclude'}
            onChange={() => setMode('exclude')}
            disabled={disabled}
          />
          <span>
            <b>Везде, кроме отмеченных</b>
            <small>
              Ничего не отмечено — акция идёт по всей стране. Отметьте города,
              где сеть её не проводит.
            </small>
          </span>
        </label>
        <label className={value.mode === 'include' ? 'on' : ''}>
          <input
            type="radio"
            checked={value.mode === 'include'}
            onChange={() => setMode('include')}
            disabled={disabled}
          />
          <span>
            <b>Только в отмеченных</b>
            <small>Акция появится ровно в этих городах и больше нигде.</small>
          </span>
        </label>
      </div>

      {value.cities.length > 0 && (
        <div className="scope-selected" aria-label="Выбранные города">
          {value.cities.map((name) => (
            <button type="button" key={name} className={`scope-city on ${value.mode}`} onClick={() => toggle(name)} disabled={disabled} aria-label={`Убрать ${name}`}>
              {name}<Icon name="close" size={13} strokeWidth={2.4} />
            </button>
          ))}
        </div>
      )}

      <div className="scope-city-search">
        <div className="scope-search-input">
          <Icon name="search" size={17} />
          <input placeholder="Найти город…" value={query} onChange={(e) => setQuery(e.target.value)} disabled={disabled} aria-label="Поиск города" />
          {query && <button type="button" onClick={() => setQuery('')} aria-label="Очистить поиск"><Icon name="close" size={16} /></button>}
        </div>
        {normalizedQuery && (
          <div className="scope-search-results">
            {matches.map((city) => (
              <button type="button" key={city.name} onClick={() => { toggle(city.name); setQuery(''); }} disabled={disabled}>
                <span><Icon name="city" size={16} />{city.name}</span>
                <small>{city.restaurants_count} точек</small>
              </button>
            ))}
            {matches.length === 0 && <div className="scope-search-empty">Город не найден или уже выбран</div>}
          </div>
        )}
      </div>

      <div className="scope-summary">{summary(value)}</div>
    </div>
  );
}

function same(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function summary(scope: PromotionScope): string {
  const list = scope.cities.join(', ');
  if (scope.mode === 'include') {
    return list ? `Показывается только: ${list}` : 'Ни одного города — акция нигде не появится';
  }
  return list ? `Вся страна, кроме: ${list}` : 'Вся страна';
}
