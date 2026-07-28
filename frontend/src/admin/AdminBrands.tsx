import { FormEvent, useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminBrand } from '../types';

interface BrandForm {
  id: number | null;
  name: string;
  color: string;
  logo_url: string;
}

const emptyForm: BrandForm = { id: null, name: '', color: '#6B9080', logo_url: '' };

export default function AdminBrands() {
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [form, setForm] = useState<BrandForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const load = () => {
    api.get<AdminBrand[]>('/admin/brands').then(setBrands).catch(() => {});
  };

  useEffect(load, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setError(null);
    const body = {
      name: form.name,
      color: form.color,
      logo_url: form.logo_url || null,
    };
    try {
      if (form.id === null) await api.post('/admin/brands', body);
      else await api.patch(`/admin/brands/${form.id}`, body);
      setForm(null);
      load();
      toast('Сохранено');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const remove = async (brand: AdminBrand) => {
    if (!window.confirm(`Удалить бренд «${brand.name}»?`)) return;
    try {
      await api.delete(`/admin/brands/${brand.id}`);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  return (
    <div>
      <h1>Бренды</h1>
      <div className="admin-toolbar">
        <button
          className="btn btn-primary btn-small"
          onClick={() => {
            setError(null);
            setForm(emptyForm);
          }}
        >
          + Новый бренд
        </button>
      </div>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Slug</th>
              <th>Точек</th>
              <th>Логотип</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {brands.map((b) => (
              <tr key={b.id}>
                <td>
                  <span className="color-dot" style={{ background: b.color }} />
                  {b.name}
                </td>
                <td>{b.slug}</td>
                <td>{b.restaurants_count}</td>
                <td>{b.logo_url ? '✓' : '—'}</td>
                <td>
                  <div className="actions">
                    <button
                      className="btn btn-ghost btn-small"
                      onClick={() => {
                        setError(null);
                        setForm({
                          id: b.id,
                          name: b.name,
                          color: b.color,
                          logo_url: b.logo_url ?? '',
                        });
                      }}
                    >
                      Изменить
                    </button>
                    <button className="btn btn-danger btn-small" onClick={() => remove(b)}>
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
              <h2>{form.id === null ? 'Новый бренд' : 'Редактировать бренд'}</h2>
              <button className="modal-close" onClick={() => setForm(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <form
                onSubmit={submit}
                style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
              >
                <div className="field">
                  <label>Название</label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </div>
                <div className="field">
                  <label>Цвет маркеров</label>
                  <input
                    type="color"
                    value={form.color}
                    onChange={(e) => setForm({ ...form, color: e.target.value })}
                    style={{ height: 44, padding: 4 }}
                  />
                </div>
                <div className="field">
                  <label>Логотип (URL, необязательно)</label>
                  <input
                    value={form.logo_url}
                    onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                    placeholder="https://…"
                  />
                </div>
                {error && <div className="form-error">{error}</div>}
                <button className="btn btn-primary">Сохранить</button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
