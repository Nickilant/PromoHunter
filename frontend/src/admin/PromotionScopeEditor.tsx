import { useEffect, useState } from 'react';

import { api } from '../api/client';
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
  const [custom, setCustom] = useState('');

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

  const addCustom = () => {
    const name = custom.trim();
    if (!name) return;
    if (!value.cities.some((c) => same(c, name))) {
      onChange({ ...value, cities: [...value.cities, name] });
    }
    setCustom('');
  };

  // Города, которых нет в справочнике, но которые уже в списке
  const known = new Set(cities.map((c) => c.name.toLowerCase()));
  const extra = value.cities.filter((c) => !known.has(c.toLowerCase()));

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

      <div className="scope-cities">
        {[...cities.map((c) => c.name), ...extra].map((name) => {
          const listed = value.cities.some((c) => same(c, name));
          return (
            <button
              type="button"
              key={name}
              className={`scope-city${listed ? ' on' : ''} ${value.mode}`}
              onClick={() => toggle(name)}
              disabled={disabled}
              aria-pressed={listed}
            >
              {name}
            </button>
          );
        })}
      </div>

      <div className="scope-custom">
        <input
          className="text-input"
          placeholder="Другой город…"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addCustom();
            }
          }}
          disabled={disabled}
        />
        <button
          type="button"
          className="btn btn-ghost btn-small"
          onClick={addCustom}
          disabled={disabled || !custom.trim()}
        >
          Добавить
        </button>
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
