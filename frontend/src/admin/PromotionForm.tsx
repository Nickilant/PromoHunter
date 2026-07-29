import { FormEvent, useState } from 'react';

import type { AdminBrand } from '../types';
import Icon from '../components/Icon';

export interface PromotionFormValue {
  brand_id: string;
  title: string;
  description: string;
  starts_at: string; // значение input[type=datetime-local]
  ends_at: string;
  is_active: boolean;
  items: { id?: number; name: string }[];
}

export function toLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

interface Props {
  brands: AdminBrand[];
  initial: PromotionFormValue;
  submitLabel: string;
  onSubmit: (value: PromotionFormValue) => Promise<void>;
  error: string | null;
}

export default function PromotionForm({
  brands,
  initial,
  submitLabel,
  onSubmit,
  error,
}: Props) {
  const [value, setValue] = useState<PromotionFormValue>(initial);
  const [sending, setSending] = useState(false);

  const set = <K extends keyof PromotionFormValue>(key: K, v: PromotionFormValue[K]) =>
    setValue((prev) => ({ ...prev, [key]: v }));

  const setItem = (index: number, name: string) =>
    set(
      'items',
      value.items.map((item, i) => (i === index ? { ...item, name } : item)),
    );

  const moveItem = (index: number, dir: -1 | 1) => {
    const next = [...value.items];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    set('items', next);
  };

  const removeItem = (index: number) =>
    set('items', value.items.filter((_, i) => i !== index));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      await onSubmit(value);
    } finally {
      setSending(false);
    }
  };

  const selectedBrand = brands.find((b) => String(b.id) === value.brand_id);

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="admin-form-grid">
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
          <label>Название</label>
          <input
            value={value.title}
            onChange={(e) => set('title', e.target.value)}
            required
          />
        </div>
        <div className="field full">
          <label>Описание</label>
          <textarea
            rows={2}
            value={value.description}
            onChange={(e) => set('description', e.target.value)}
          />
        </div>
        <div className="field">
          <label>Начало (пусто — бессрочно)</label>
          <input
            type="datetime-local"
            value={value.starts_at}
            onChange={(e) => set('starts_at', e.target.value)}
          />
        </div>
        <div className="field">
          <label>Окончание (пусто — бессрочно)</label>
          <input
            type="datetime-local"
            value={value.ends_at}
            onChange={(e) => set('ends_at', e.target.value)}
          />
        </div>
        <div className="field full">
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={value.is_active}
              onChange={(e) => set('is_active', e.target.checked)}
              style={{ width: 'auto' }}
            />
            Акция активна
          </label>
        </div>
      </div>

      <div className="field">
        <label>Товары</label>
        <div className="items-editor">
          {value.items.map((item, i) => (
            <div className="item-line" key={item.id ?? `new-${i}`}>
              <input
                value={item.name}
                onChange={(e) => setItem(i, e.target.value)}
                placeholder="Название товара"
                required
              />
              <button type="button" onClick={() => moveItem(i, -1)} title="Вверх">
                <Icon name="arrowUp" size={16} />
              </button>
              <button type="button" onClick={() => moveItem(i, 1)} title="Вниз">
                <Icon name="arrowDown" size={16} />
              </button>
              <button
                type="button"
                onClick={() => removeItem(i)}
                title="Удалить"
                disabled={value.items.length <= 1}
              >
                <Icon name="close" size={20} />
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={() => set('items', [...value.items, { name: '' }])}
          >
            + Добавить товар
          </button>
        </div>
      </div>

      {selectedBrand && (
        <div className="form-success">
          Акция появится во всех точках сети «{selectedBrand.name}» — сейчас их{' '}
          {selectedBrand.restaurants_count}
        </div>
      )}
      {error && <div className="form-error">{error}</div>}

      <button className="btn btn-primary" disabled={sending}>
        {sending ? 'Сохраняем…' : submitLabel}
      </button>
    </form>
  );
}
