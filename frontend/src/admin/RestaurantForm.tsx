import { FormEvent, useState } from 'react';

import MapPickerWithSearch from '../components/MapPickerWithSearch';
import type { AdminBrand } from '../types';

export interface RestaurantFormValue {
  brand_id: string;
  title: string;
  city: string;
  address: string;
  lat: string;
  lng: string;
  is_active: boolean;
}

interface Props {
  brands: AdminBrand[];
  initial: RestaurantFormValue;
  submitLabel: string;
  onSubmit: (value: RestaurantFormValue) => Promise<void>;
  error: string | null;
}

export default function RestaurantForm({
  brands,
  initial,
  submitLabel,
  onSubmit,
  error,
}: Props) {
  const [value, setValue] = useState<RestaurantFormValue>(initial);
  const [sending, setSending] = useState(false);

  const set = <K extends keyof RestaurantFormValue>(
    key: K,
    v: RestaurantFormValue[K],
  ) => setValue((prev) => ({ ...prev, [key]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      await onSubmit(value);
    } finally {
      setSending(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <div className="restaurant-editor">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="field">
            <label>Бренд</label>
            <select
              value={value.brand_id}
              onChange={(e) => set('brand_id', e.target.value)}
              required
            >
              <option value="" disabled>
                Выберите…
              </option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Название точки (необязательно)</label>
            <input
              value={value.title}
              onChange={(e) => set('title', e.target.value)}
              placeholder="ТЦ Галерея, 2 этаж"
            />
          </div>
          <div className="field">
            <label>Город</label>
            <input
              value={value.city}
              onChange={(e) => set('city', e.target.value)}
              placeholder="Санкт-Петербург"
              required
            />
          </div>
          <div className="field">
            <label>Адрес</label>
            <input
              value={value.address}
              onChange={(e) => set('address', e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label>Широта</label>
            <input
              value={value.lat}
              onChange={(e) => set('lat', e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label>Долгота</label>
            <input
              value={value.lng}
              onChange={(e) => set('lng', e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={value.is_active}
                onChange={(e) => set('is_active', e.target.checked)}
                style={{ width: 'auto' }}
              />
              Точка активна
            </label>
          </div>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary" disabled={sending}>
            {sending ? 'Сохраняем…' : submitLabel}
          </button>
        </div>
        <MapPickerWithSearch
          lat={value.lat ? Number(value.lat) : null}
          lng={value.lng ? Number(value.lng) : null}
          city={value.city || null}
          onPick={(lat, lng) =>
            setValue((prev) => ({
              ...prev,
              lat: lat.toFixed(6),
              lng: lng.toFixed(6),
            }))
          }
        />
      </div>
    </form>
  );
}
