import { FormEvent, useEffect, useMemo, useState } from 'react';

import { api } from '../api/client';
import Icon from '../components/Icon';
import { useToast } from '../components/Toast';
import type { AdminBrand, AdminCity, OsmImportBatch, OsmImportCommitResult, OsmImportPoint } from '../types';

const MISSING_ADDRESS = 'Адрес не указан в OSM';

function selectableIds(batch: OsmImportBatch): number[] {
  return batch.points
    .filter((point) => !point.duplicate_restaurant_id && !point.imported_restaurant_id && point.address !== MISSING_ADDRESS)
    .map((point) => point.id);
}

export default function AdminOsmImports() {
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [cities, setCities] = useState<AdminCity[]>([]);
  const [batches, setBatches] = useState<OsmImportBatch[]>([]);
  const [active, setActive] = useState<OsmImportBatch | null>(null);
  const [brandId, setBrandId] = useState('');
  const [city, setCity] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: number; title: string; address: string } | null>(null);
  const toast = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const [brandRows, cityRows, imports] = await Promise.all([
        api.get<AdminBrand[]>('/admin/brands'),
        api.get<AdminCity[]>('/admin/cities'),
        api.get<OsmImportBatch[]>('/admin/osm-imports'),
      ]);
      setBrands(brandRows);
      setCities(cityRows.filter((item) => item.is_active));
      setBatches(imports);
      if (!brandId && brandRows.length) setBrandId(String(brandRows[0].id));
      if (!city && cityRows.length) setCity(cityRows[0].name);
      if (!active && imports.length) chooseBatch(imports[0]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const chooseBatch = (batch: OsmImportBatch) => {
    setActive(batch);
    setSelected(new Set(selectableIds(batch)));
    setError(null);
  };

  const startImport = async (event: FormEvent) => {
    event.preventDefault();
    setFetching(true);
    setError(null);
    try {
      const batch = await api.post<OsmImportBatch>('/admin/osm-imports', {
        brand_id: Number(brandId),
        city,
        query: query.trim() || null,
      });
      setBatches((current) => [batch, ...current]);
      chooseBatch(batch);
      toast(`OSM нашёл точек: ${batch.points.length}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось получить точки из OSM');
    } finally {
      setFetching(false);
    }
  };

  const toggle = (id: number) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const available = useMemo(() => (active ? selectableIds(active) : []), [active]);
  const allSelected = available.length > 0 && available.every((id) => selected.has(id));

  const commit = async () => {
    if (!active || selected.size === 0) return;
    setCommitting(true);
    setError(null);
    try {
      const result = await api.post<OsmImportCommitResult>(`/admin/osm-imports/${active.id}/commit`, {
        point_ids: [...selected],
      });
      const refreshed = await api.get<OsmImportBatch>(`/admin/osm-imports/${active.id}`);
      setActive(refreshed);
      setBatches((current) => current.map((item) => (item.id === refreshed.id ? refreshed : item)));
      setSelected(new Set());
      toast(`Добавлено: ${result.imported}${result.skipped ? `, пропущено: ${result.skipped}` : ''}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось импортировать точки');
    } finally {
      setCommitting(false);
    }
  };

  const savePoint = async (point: OsmImportPoint) => {
    if (!active || !editing || editing.id !== point.id) return;
    setError(null);
    try {
      const updated = await api.patch<OsmImportPoint>(`/admin/osm-imports/${active.id}/points/${point.id}`, {
        title: editing.title.trim() || null,
        address: editing.address.trim(),
      });
      const updateBatch = (batch: OsmImportBatch): OsmImportBatch => ({
        ...batch,
        points: batch.points.map((item) => (item.id === updated.id ? updated : item)),
      });
      const next = updateBatch(active);
      setActive(next);
      setBatches((current) => current.map((batch) => (batch.id === next.id ? next : batch)));
      if (!updated.duplicate_restaurant_id) setSelected((current) => new Set(current).add(updated.id));
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить точку');
    }
  };

  const removeBatch = async () => {
    if (!active || !window.confirm('Удалить этот временный набор? Уже импортированные рестораны останутся.')) return;
    await api.delete(`/admin/osm-imports/${active.id}`);
    const remaining = batches.filter((item) => item.id !== active.id);
    setBatches(remaining);
    setActive(remaining[0] ?? null);
    setSelected(new Set(remaining[0] ? selectableIds(remaining[0]) : []));
  };

  if (loading) return <div className="admin-empty">Загружаем импорты…</div>;

  return (
    <div className="osm-import-page">
      <div className="osm-import-heading">
        <div>
          <h1>Импорт точек из OSM</h1>
          <p>Сначала точки попадают во временный список на 7 дней. Проверьте адреса и выберите, что переносить в приложение.</p>
        </div>
        <a className="osm-attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          © OpenStreetMap contributors
        </a>
      </div>

      <form className="osm-import-form" onSubmit={startImport}>
        <div className="field">
          <label htmlFor="osm-brand">Бренд</label>
          <select id="osm-brand" value={brandId} onChange={(event) => setBrandId(event.target.value)} required>
            {brands.map((brand) => <option key={brand.id} value={brand.id}>{brand.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="osm-city">Город</label>
          <select id="osm-city" value={city} onChange={(event) => setCity(event.target.value)} required>
            {cities.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
          </select>
        </div>
        <div className="field osm-query-field">
          <label htmlFor="osm-query">Название в OSM</label>
          <input id="osm-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="По умолчанию — название бренда" />
        </div>
        <button className="btn btn-primary" disabled={fetching || !brandId || !city}>
          <Icon name="search" size={17} />
          {fetching ? 'Ищем в OSM…' : 'Найти точки'}
        </button>
      </form>
      {error && <div className="form-error osm-import-error">{error}</div>}

      <div className="osm-import-workspace">
        <aside className="osm-batch-list" aria-label="История временных импортов">
          <div className="osm-section-label">Последние поиски</div>
          {batches.map((batch) => (
            <button key={batch.id} className={active?.id === batch.id ? 'active' : ''} onClick={() => chooseBatch(batch)}>
              <strong>{batch.brand.name}</strong>
              <span>{batch.city} · {batch.points.length} точек</span>
            </button>
          ))}
          {batches.length === 0 && <div className="admin-empty">Поисков ещё не было</div>}
        </aside>

        <section className="osm-preview">
          {!active ? (
            <div className="osm-preview-empty"><Icon name="inbox" size={42} /><strong>Создайте первый импорт</strong><span>Выберите бренд и город выше.</span></div>
          ) : (
            <>
              <div className="osm-preview-toolbar">
                <div>
                  <strong>{active.brand.name} · {active.city}</strong>
                  <span>{available.length} можно добавить · {active.points.length - available.length} дублей или уже добавлены</span>
                </div>
                <div className="actions">
                  <button className="btn btn-ghost btn-small" onClick={() => setSelected(new Set(allSelected ? [] : available))} disabled={!available.length}>
                    {allSelected ? 'Снять выбор' : 'Выбрать новые'}
                  </button>
                  <button className="btn btn-danger btn-small" onClick={removeBatch}>Удалить набор</button>
                </div>
              </div>
              <div className="osm-point-list">
                {active.points.map((point) => {
                  const missingAddress = point.address === MISSING_ADDRESS;
                  const blocked = Boolean(point.duplicate_restaurant_id || point.imported_restaurant_id || missingAddress);
                  return (
                    <div className={`osm-point-row${blocked ? ' blocked' : ''}`} key={point.id}>
                      <input type="checkbox" checked={selected.has(point.id)} disabled={blocked} onChange={() => toggle(point.id)} />
                      {editing?.id === point.id ? (
                        <div className="osm-point-editor">
                          <input value={editing.title} onChange={(event) => setEditing({ ...editing, title: event.target.value })} placeholder="Название точки" />
                          <input autoFocus value={editing.address} onChange={(event) => setEditing({ ...editing, address: event.target.value })} placeholder="Улица и номер дома" />
                          <div className="actions">
                            <button className="btn btn-primary btn-small" onClick={() => savePoint(point)} disabled={editing.address.trim().length < 3}>Сохранить</button>
                            <button className="btn btn-ghost btn-small" onClick={() => setEditing(null)}>Отмена</button>
                          </div>
                        </div>
                      ) : (
                        <span className="osm-point-main">
                          <strong>{point.title || active.brand.name}</strong>
                          <span>{point.address}</span>
                          <small>{point.lat.toFixed(5)}, {point.lng.toFixed(5)}</small>
                        </span>
                      )}
                      {point.imported_restaurant_id ? <span className="tag ok">Добавлена</span> : point.duplicate_restaurant_id ? <span className="tag warn">Похожая точка уже есть</span> : missingAddress ? <button className="btn btn-ghost btn-small" onClick={() => setEditing({ id: point.id, title: point.title ?? '', address: '' })}>Указать адрес</button> : <span className="tag">Новая</span>}
                      <a href={`https://www.openstreetmap.org/${point.osm_type}/${point.osm_id}`} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} aria-label="Открыть объект в OpenStreetMap">
                        <Icon name="map" size={18} />
                      </a>
                    </div>
                  );
                })}
                {active.points.length === 0 && <div className="admin-empty">По этому названию точек в границах города не найдено.</div>}
              </div>
              <div className="osm-commit-bar">
                <span>Выбрано: {selected.size}</span>
                <button className="btn btn-primary" disabled={!selected.size || committing} onClick={commit}>
                  <Icon name="check" size={17} />
                  {committing ? 'Добавляем…' : 'Добавить выбранные'}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
