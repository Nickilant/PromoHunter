import { FormEvent, useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminBrand } from '../types';
import Icon from '../components/Icon';
import AdminSearch, { matches } from './AdminSearch';

interface BrandForm {
  id: number | null;
  name: string;
  color: string;
  logo_url: string;
  is_public: boolean;
}

type LogoMode = 'url' | 'file';

const emptyForm: BrandForm = {
  id: null,
  name: '',
  color: '#6B9080',
  logo_url: '',
  is_public: false,
};

export default function AdminBrands() {
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [query, setQuery] = useState('');
  const [form, setForm] = useState<BrandForm | null>(null);
  const [logoMode, setLogoMode] = useState<LogoMode>('url');
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
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
    setSaving(true);
    try {
      let logoUrl = form.logo_url || null;
      if (logoMode === 'file') {
        if (!logoFile) throw new Error('Выберите файл логотипа');
        const data = new FormData();
        data.append('logo', logoFile);
        const uploaded = await api.upload<{ logo_url: string }>('/admin/brand-logos', data);
        logoUrl = uploaded.logo_url;
      }
      const body = {
        name: form.name,
        color: form.color,
        logo_url: logoUrl,
        is_public: form.is_public,
      };
      if (form.id === null) await api.post('/admin/brands', body);
      else await api.patch(`/admin/brands/${form.id}`, body);
      setForm(null);
      setLogoFile(null);
      load();
      toast('Сохранено');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSaving(false);
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

  const shown = brands.filter((b) => matches(query, b.name, b.slug));

  return (
    <div>
      <h1>Бренды</h1>
      <div className="admin-toolbar">
        <button
          className="btn btn-primary btn-small"
          onClick={() => {
            setError(null);
            setForm(emptyForm);
            setLogoMode('url');
            setLogoFile(null);
          }}
        >
          + Новый бренд
        </button>
      </div>
      <AdminSearch
        value={query}
        onChange={setQuery}
        placeholder="Поиск по названию или slug"
        found={shown.length}
        total={brands.length}
      />

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Slug</th>
              <th>Точек</th>
              <th>Логотип</th>
              <th>Публикация</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {shown.map((b) => (
              <tr key={b.id}>
                <td>
                  <span className="color-dot" style={{ background: b.color }} />
                  {b.name}
                </td>
                <td>{b.slug}</td>
                <td>{b.restaurants_count}</td>
                <td>
                  {b.logo_url ? (
                    <span role="img" aria-label="Логотип загружен">
                      <Icon name="check" size={16} />
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td>
                  <span className={`tag ${b.is_public ? 'ok' : 'warn'}`}>
                    {b.is_public ? 'Виден всем' : 'Только команде'}
                  </span>
                </td>
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
                          is_public: b.is_public,
                        });
                        setLogoMode('url');
                        setLogoFile(null);
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
              <button className="modal-close" onClick={() => setForm(null)} aria-label="Закрыть">
                <Icon name="close" size={20} />
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
                <fieldset className="brand-logo-field">
                  <legend>Логотип</legend>
                  <div className="brand-logo-modes" role="radiogroup" aria-label="Источник логотипа">
                    <label className={logoMode === 'url' ? 'on' : ''}>
                      <input
                        type="radio"
                        name="logo-mode"
                        checked={logoMode === 'url'}
                        onChange={() => setLogoMode('url')}
                      />
                      Ссылка
                    </label>
                    <label className={logoMode === 'file' ? 'on' : ''}>
                      <input
                        type="radio"
                        name="logo-mode"
                        checked={logoMode === 'file'}
                        onChange={() => setLogoMode('file')}
                      />
                      Файл
                    </label>
                  </div>
                  {logoMode === 'url' ? (
                    <input
                      type="url"
                      value={form.logo_url}
                      onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                      placeholder="https://…"
                    />
                  ) : (
                    <div className="brand-logo-upload">
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={(e) => setLogoFile(e.target.files?.[0] ?? null)}
                        required
                      />
                      <small>PNG, JPEG или WebP, не больше 5 МБ</small>
                    </div>
                  )}
                </fieldset>
                <label className="brand-visibility-toggle">
                  <input
                    type="checkbox"
                    checked={form.is_public}
                    onChange={(e) => setForm({ ...form, is_public: e.target.checked })}
                  />
                  <span>
                    <strong>Показывать бренд пользователям</strong>
                    <small>
                      Если выключить, бренд, его точки и акции увидят только администраторы и модераторы.
                    </small>
                  </span>
                </label>
                {error && <div className="form-error">{error}</div>}
                <button className="btn btn-primary" disabled={saving}>
                  {saving ? 'Сохраняем…' : 'Сохранить'}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
