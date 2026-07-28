import { FormEvent, useEffect, useState } from 'react';

import { api } from '../api/client';
import { LocationPickerMap } from '../components/MapView';
import { useToast } from '../components/Toast';
import type { AdminBrand, AdminRestaurant } from '../types';

interface RestForm {
  id: number | null;
  brand_id: string;
  title: string;
  address: string;
  lat: string;
  lng: string;
  is_active: boolean;
}

const emptyForm: RestForm = {
  id: null,
  brand_id: '',
  title: '',
  address: '',
  lat: '',
  lng: '',
  is_active: true,
};

export default function AdminRestaurants() {
  const [restaurants, setRestaurants] = useState<AdminRestaurant[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [brandFilter, setBrandFilter] = useState('');
  const [form, setForm] = useState<RestForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const load = (filter: string) => {
    const params = filter ? `?brand_id=${filter}` : '';
    api
      .get<AdminRestaurant[]>(`/admin/restaurants${params}`)
      .then(setRestaurants)
      .catch(() => {});
  };

  useEffect(() => {
    api.get<AdminBrand[]>('/admin/brands').then(setBrands).catch(() => {});
  }, []);

  useEffect(() => load(brandFilter), [brandFilter]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setError(null);
    const body = {
      brand_id: Number(form.brand_id),
      title: form.title || null,
      address: form.address,
      lat: Number(form.lat),
      lng: Number(form.lng),
      is_active: form.is_active,
    };
    if (Number.isNaN(body.lat) || Number.isNaN(body.lng)) {
      setError('Укажите координаты: кликните по карте или введите вручную');
      return;
    }
    try {
      if (form.id === null) await api.post('/admin/restaurants', body);
      else await api.patch(`/admin/restaurants/${form.id}`, body);
      setForm(null);
      load(brandFilter);
      toast('Сохранено');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const remove = async (r: AdminRestaurant) => {
    if (!window.confirm(`Удалить точку «${r.address}»? Отчёты по ней тоже удалятся.`))
      return;
    try {
      await api.delete(`/admin/restaurants/${r.id}`);
      load(brandFilter);
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  return (
    <div>
      <h1>Рестораны</h1>
      <div className="admin-toolbar">
        <button
          className="btn btn-primary btn-small"
          onClick={() => {
            setError(null);
            setForm(emptyForm);
          }}
        >
          + Новая точка
        </button>
        <select value={brandFilter} onChange={(e) => setBrandFilter(e.target.value)}>
          <option value="">Все бренды</option>
          {brands.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Бренд</th>
              <th>Название</th>
              <th>Адрес</th>
              <th>Координаты</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {restaurants.map((r) => (
              <tr key={r.id}>
                <td>
                  <span className="color-dot" style={{ background: r.brand.color }} />
                  {r.brand.name}
                </td>
                <td>{r.title || '—'}</td>
                <td>{r.address}</td>
                <td>
                  {r.lat.toFixed(4)}, {r.lng.toFixed(4)}
                </td>
                <td>
                  <span className={`tag ${r.is_active ? 'ok' : 'error'}`}>
                    {r.is_active ? 'Активна' : 'Скрыта'}
                  </span>
                </td>
                <td>
                  <div className="actions">
                    <button
                      className="btn btn-ghost btn-small"
                      onClick={() => {
                        setError(null);
                        setForm({
                          id: r.id,
                          brand_id: String(r.brand.id),
                          title: r.title ?? '',
                          address: r.address,
                          lat: String(r.lat),
                          lng: String(r.lng),
                          is_active: r.is_active,
                        });
                      }}
                    >
                      Изменить
                    </button>
                    <button className="btn btn-danger btn-small" onClick={() => remove(r)}>
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {form && (
        <div className="modal-overlay" onClick={() => setForm(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2>{form.id === null ? 'Новая точка' : 'Редактировать точку'}</h2>
              <button className="modal-close" onClick={() => setForm(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <form onSubmit={submit}>
                <div className="restaurant-editor">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div className="field">
                      <label>Бренд</label>
                      <select
                        value={form.brand_id}
                        onChange={(e) => setForm({ ...form, brand_id: e.target.value })}
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
                        value={form.title}
                        onChange={(e) => setForm({ ...form, title: e.target.value })}
                        placeholder="ТЦ Галерея, 2 этаж"
                      />
                    </div>
                    <div className="field">
                      <label>Адрес</label>
                      <input
                        value={form.address}
                        onChange={(e) => setForm({ ...form, address: e.target.value })}
                        required
                      />
                    </div>
                    <div className="field">
                      <label>Широта</label>
                      <input
                        value={form.lat}
                        onChange={(e) => setForm({ ...form, lat: e.target.value })}
                        required
                      />
                    </div>
                    <div className="field">
                      <label>Долгота</label>
                      <input
                        value={form.lng}
                        onChange={(e) => setForm({ ...form, lng: e.target.value })}
                        required
                      />
                    </div>
                    <div className="field">
                      <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <input
                          type="checkbox"
                          checked={form.is_active}
                          onChange={(e) =>
                            setForm({ ...form, is_active: e.target.checked })
                          }
                          style={{ width: 'auto' }}
                        />
                        Точка активна
                      </label>
                    </div>
                    {error && <div className="form-error">{error}</div>}
                    <button className="btn btn-primary">Сохранить</button>
                  </div>
                  <div className="map-picker">
                    <LocationPickerMap
                      lat={form.lat ? Number(form.lat) : null}
                      lng={form.lng ? Number(form.lng) : null}
                      onPick={(lat, lng) =>
                        setForm((prev) =>
                          prev
                            ? { ...prev, lat: lat.toFixed(6), lng: lng.toFixed(6) }
                            : prev,
                        )
                      }
                    />
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
