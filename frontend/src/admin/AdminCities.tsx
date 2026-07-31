import { FormEvent, useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminCity, CityBulkResult } from '../types';
import AdminSearch, { matches } from './AdminSearch';
import { useStaffScope } from './useStaffScope';

/**
 * Справочник городов. Город заводится до первой точки: человек выбирает его
 * при регистрации и сам присылает заявку на первый ресторан.
 */
export default function AdminCities() {
  const [cities, setCities] = useState<AdminCity[]>([]);
  const [query, setQuery] = useState('');
  const [name, setName] = useState('');
  const [bulk, setBulk] = useState('');
  const [bulkOpen, setBulkOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scope = useStaffScope();
  const toast = useToast();

  const load = () => {
    api.get<AdminCity[]>('/admin/cities').then(setCities).catch(() => {});
  };

  useEffect(load, []);

  const isGlobal = !scope || scope.is_global;

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await api.post('/admin/cities', { name });
      setName('');
      load();
      toast('Город добавлен');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSending(false);
    }
  };

  const addBulk = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      const res = await api.post<CityBulkResult>('/admin/cities/bulk', { names: bulk });
      setBulk('');
      setBulkOpen(false);
      load();
      toast(
        res.skipped.length
          ? `Добавлено ${res.added.length}, пропущено ${res.skipped.length} (уже были)`
          : `Добавлено ${res.added.length}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSending(false);
    }
  };

  const patch = async (id: number, body: { name?: string; is_active?: boolean }) => {
    try {
      await api.patch(`/admin/cities/${id}`, body);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const remove = async (city: AdminCity) => {
    if (!confirm(`Удалить город «${city.name}»?`)) return;
    try {
      await api.delete(`/admin/cities/${city.id}`);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const rename = (city: AdminCity) => {
    const next = prompt('Новое название города', city.name);
    if (next && next.trim() && next.trim() !== city.name) {
      patch(city.id, { name: next.trim() });
    }
  };

  const shown = cities.filter((c) => matches(query, c.name));

  return (
    <div>
      <h1>Города</h1>

      {isGlobal && (
        <>
          <form onSubmit={add} className="admin-toolbar">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название города"
              required
            />
            <button className="btn btn-primary btn-small" disabled={sending}>
              Добавить
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => setBulkOpen(!bulkOpen)}
            >
              {bulkOpen ? 'Свернуть список' : 'Добавить списком'}
            </button>
          </form>

          {bulkOpen && (
            <form onSubmit={addBulk} className="field" style={{ marginBottom: 16 }}>
              <label>Города через запятую, точку с запятой или с новой строки</label>
              <textarea
                rows={6}
                value={bulk}
                onChange={(e) => setBulk(e.target.value)}
                placeholder={'Казань, Уфа, Самара\nОмск\nТомск'}
                required
              />
              <button
                className="btn btn-primary btn-small"
                style={{ marginTop: 8 }}
                disabled={sending}
              >
                {sending ? 'Добавляем…' : 'Добавить все'}
              </button>
            </form>
          )}
          {error && <div className="form-error">{error}</div>}
        </>
      )}

      <AdminSearch
        value={query}
        onChange={setQuery}
        placeholder="Поиск по названию города"
        found={shown.length}
        total={cities.length}
      />

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Город</th>
              <th>Точек</th>
              <th>Статус</th>
              {isGlobal && <th></th>}
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.restaurants_count}</td>
                <td>
                  <span className={`tag ${c.is_active ? 'ok' : 'warn'}`}>
                    {c.is_active ? 'Виден' : 'Скрыт'}
                  </span>
                </td>
                {isGlobal && (
                  <td>
                    <div className="actions">
                      <button className="btn btn-ghost btn-small" onClick={() => rename(c)}>
                        Переименовать
                      </button>
                      <button
                        className="btn btn-ghost btn-small"
                        onClick={() => patch(c.id, { is_active: !c.is_active })}
                      >
                        {c.is_active ? 'Скрыть' : 'Показать'}
                      </button>
                      <button
                        className="btn btn-danger btn-small"
                        disabled={c.restaurants_count > 0}
                        title={
                          c.restaurants_count > 0
                            ? 'В городе есть точки — сначала уберите их или скройте город'
                            : undefined
                        }
                        onClick={() => remove(c)}
                      >
                        Удалить
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && (
          <div className="admin-empty">
            {query ? 'Ничего не нашлось' : 'Городов пока нет'}
          </div>
        )}
      </div>
    </div>
  );
}
