import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminBrand, AdminPromotion } from '../types';
import { formatDate } from '../utils/time';
import PromotionForm, {
  fromLocalInput,
  PromotionFormValue,
  toLocalInput,
} from './PromotionForm';

export default function AdminPromotions() {
  const [promotions, setPromotions] = useState<AdminPromotion[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [brandFilter, setBrandFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [form, setForm] = useState<{ id: number | null; value: PromotionFormValue } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const load = () => {
    const params = new URLSearchParams();
    if (brandFilter) params.set('brand_id', brandFilter);
    if (activeFilter) params.set('is_active', activeFilter);
    const qs = params.toString();
    api
      .get<AdminPromotion[]>(`/admin/promotions${qs ? `?${qs}` : ''}`)
      .then(setPromotions)
      .catch(() => {});
  };

  useEffect(() => {
    api.get<AdminBrand[]>('/admin/brands').then(setBrands).catch(() => {});
  }, []);

  useEffect(load, [brandFilter, activeFilter]);

  const save = async (value: PromotionFormValue) => {
    setError(null);
    const body = {
      brand_id: Number(value.brand_id),
      title: value.title,
      description: value.description || null,
      starts_at: fromLocalInput(value.starts_at),
      ends_at: fromLocalInput(value.ends_at),
      is_active: value.is_active,
      items: value.items.map((i) => ({ id: i.id, name: i.name })),
    };
    const brand = brands.find((b) => b.id === body.brand_id);
    try {
      if (form?.id == null) await api.post('/admin/promotions', body);
      else await api.patch(`/admin/promotions/${form.id}`, body);
      setForm(null);
      load();
      toast(
        brand
          ? `Сохранено. Акция видна во всех точках «${brand.name}» (${brand.restaurants_count})`
          : 'Сохранено',
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const remove = async (p: AdminPromotion) => {
    if (
      !window.confirm(
        `Удалить акцию «${p.title}»? Товары и отчёты по ней тоже удалятся.`,
      )
    )
      return;
    try {
      await api.delete(`/admin/promotions/${p.id}`);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const openNew = () => {
    setError(null);
    setForm({
      id: null,
      value: {
        brand_id: '',
        title: '',
        description: '',
        starts_at: '',
        ends_at: '',
        is_active: true,
        items: [{ name: '' }],
      },
    });
  };

  const openEdit = (p: AdminPromotion) => {
    setError(null);
    setForm({
      id: p.id,
      value: {
        brand_id: String(p.brand.id),
        title: p.title,
        description: p.description ?? '',
        starts_at: toLocalInput(p.starts_at),
        ends_at: toLocalInput(p.ends_at),
        is_active: p.is_active,
        items: p.items.map((i) => ({ id: i.id, name: i.name })),
      },
    });
  };

  return (
    <div>
      <h1>Акции</h1>
      <div className="admin-toolbar">
        <button className="btn btn-primary btn-small" onClick={openNew}>
          + Новая акция
        </button>
        <select value={brandFilter} onChange={(e) => setBrandFilter(e.target.value)}>
          <option value="">Все бренды</option>
          {brands.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}>
          <option value="">Все статусы</option>
          <option value="true">Активные</option>
          <option value="false">Выключенные</option>
        </select>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Бренд</th>
              <th>Название</th>
              <th>Товаров</th>
              <th>Период</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {promotions.map((p) => (
              <tr key={p.id}>
                <td>
                  <span className="color-dot" style={{ background: p.brand.color }} />
                  {p.brand.name}
                </td>
                <td>{p.title}</td>
                <td>{p.items.length}</td>
                <td>
                  {formatDate(p.starts_at)} — {formatDate(p.ends_at)}
                </td>
                <td>
                  <span className={`tag ${p.is_active ? 'ok' : 'error'}`}>
                    {p.is_active ? 'Активна' : 'Выключена'}
                  </span>
                </td>
                <td>
                  <div className="actions">
                    <button
                      className="btn btn-ghost btn-small"
                      onClick={() => openEdit(p)}
                    >
                      Изменить
                    </button>
                    <button
                      className="btn btn-danger btn-small"
                      onClick={() => remove(p)}
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

      {form && (
        <div className="modal-overlay" onClick={() => setForm(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2>{form.id === null ? 'Новая акция' : 'Редактировать акцию'}</h2>
              <button className="modal-close" onClick={() => setForm(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <PromotionForm
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
