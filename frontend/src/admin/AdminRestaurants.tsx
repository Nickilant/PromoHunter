import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminBrand, AdminRestaurant } from '../types';
import CollapsibleGroup from './CollapsibleGroup';
import RestaurantForm, { RestaurantFormValue } from './RestaurantForm';

const emptyForm: RestaurantFormValue = {
  brand_id: '',
  title: '',
  city: '',
  address: '',
  lat: '',
  lng: '',
  is_active: true,
};

export default function AdminRestaurants() {
  const [restaurants, setRestaurants] = useState<AdminRestaurant[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [brandFilter, setBrandFilter] = useState('');
  const [form, setForm] = useState<{ id: number | null; value: RestaurantFormValue } | null>(
    null,
  );
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

  const save = async (value: RestaurantFormValue) => {
    setError(null);
    const body = {
      brand_id: Number(value.brand_id),
      title: value.title || null,
      city: value.city,
      address: value.address,
      lat: Number(value.lat),
      lng: Number(value.lng),
      is_active: value.is_active,
    };
    if (Number.isNaN(body.lat) || Number.isNaN(body.lng)) {
      setError('Укажите координаты: найдите адрес и кликните по карте');
      return;
    }
    try {
      if (form?.id == null) await api.post('/admin/restaurants', body);
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

  // Группировка по брендам, чтобы не искать по общему списку
  const groups = new Map<number, AdminRestaurant[]>();
  for (const r of restaurants) {
    const list = groups.get(r.brand.id) ?? [];
    list.push(r);
    groups.set(r.brand.id, list);
  }

  return (
    <div>
      <h1>Рестораны</h1>
      <div className="admin-toolbar">
        <button
          className="btn btn-primary btn-small"
          onClick={() => {
            setError(null);
            setForm({ id: null, value: emptyForm });
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

      {[...groups.entries()].map(([brandId, list]) => (
        <CollapsibleGroup
          key={brandId}
          title={list[0].brand.name}
          color={list[0].brand.color}
          count={list.length}
        >
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Город</th>
                  <th>Адрес</th>
                  <th>Координаты</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.id}>
                    <td>{r.title || '—'}</td>
                    <td>{r.city}</td>
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
                              value: {
                                brand_id: String(r.brand.id),
                                title: r.title ?? '',
                                city: r.city,
                                address: r.address,
                                lat: String(r.lat),
                                lng: String(r.lng),
                                is_active: r.is_active,
                              },
                            });
                          }}
                        >
                          Изменить
                        </button>
                        <button
                          className="btn btn-danger btn-small"
                          onClick={() => remove(r)}
                        >
                          Удалить
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleGroup>
      ))}

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
              <RestaurantForm
                brands={brands}
                initial={form.value}
                submitLabel="Сохранить"
                onSubmit={save}
                error={error}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
