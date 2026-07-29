import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import type { Brand, RestaurantListItem } from '../types';
import Icon from '../components/Icon';

export default function SuggestPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [restaurants, setRestaurants] = useState<RestaurantListItem[]>([]);
  const [brandChoice, setBrandChoice] = useState<string>(''); // id или 'other'
  const [brandNameRaw, setBrandNameRaw] = useState('');
  const [restaurantId, setRestaurantId] = useState<string>('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [itemsRaw, setItemsRaw] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<Brand[]>('/brands').then(setBrands).catch(() => {});
  }, []);

  useEffect(() => {
    const isBrand = brandChoice && brandChoice !== 'other';
    if (!isBrand) {
      setRestaurants([]);
      setRestaurantId('');
      return;
    }
    api
      .get<RestaurantListItem[]>(`/restaurants?brand_id=${brandChoice}`)
      .then(setRestaurants)
      .catch(() => {});
  }, [brandChoice]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await api.post('/suggestions', {
        brand_id: brandChoice && brandChoice !== 'other' ? Number(brandChoice) : null,
        brand_name_raw: brandChoice === 'other' ? brandNameRaw : null,
        restaurant_id: restaurantId ? Number(restaurantId) : null,
        title,
        description: description || null,
        items_raw: itemsRaw,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не получилось отправить');
    } finally {
      setSending(false);
    }
  };

  if (done) {
    return (
      <div className="page">
        <div className="empty-state">
          <div className="big success"><Icon name="send" size={44} strokeWidth={1.4} /></div>
          <h2>Отправлено на модерацию</h2>
          <div>
            Спасибо! Модератор проверит заявку, статус можно смотреть в профиле.
          </div>
          <Link to="/profile" className="btn btn-primary">
            Мои заявки
          </Link>
          <Link to="/">На главную</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate(-1)} aria-label="Назад">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h1>Заявить акцию</h1>
      </div>
      <form
        onSubmit={submit}
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <div className="field">
          <label>Бренд (сеть)</label>
          <select
            value={brandChoice}
            onChange={(e) => setBrandChoice(e.target.value)}
            required
          >
            <option value="" disabled>
              Выберите сеть…
            </option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
            <option value="other">Другая (ввести название)</option>
          </select>
        </div>

        {brandChoice === 'other' && (
          <div className="field">
            <label>Название сети</label>
            <input
              value={brandNameRaw}
              onChange={(e) => setBrandNameRaw(e.target.value)}
              placeholder="Например, Теремок"
              required
            />
          </div>
        )}

        {restaurants.length > 0 && (
          <div className="field">
            <label>Где заметили (необязательно)</label>
            <select
              value={restaurantId}
              onChange={(e) => setRestaurantId(e.target.value)}
            >
              <option value="">Не важно / не помню</option>
              {restaurants.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title ? `${r.title} — ` : ''}
                  {r.address}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="field">
          <label>Название акции</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Например, Наборы с игрушками"
            required
          />
        </div>

        <div className="field">
          <label>Описание (необязательно)</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Что это за акция, при каких условиях действует"
          />
        </div>

        <div className="field">
          <label>Товары</label>
          <textarea
            rows={4}
            value={itemsRaw}
            onChange={(e) => setItemsRaw(e.target.value)}
            placeholder={'По одному в строке, например:\nСтакан красный\nСтакан синий'}
            required
          />
          <div className="hint">Каждый товар — с новой строки</div>
        </div>

        {error && <div className="form-error">{error}</div>}

        <button className="btn btn-accent btn-block" disabled={sending}>
          {sending ? 'Отправляем…' : 'Отправить на модерацию'}
        </button>
      </form>
    </div>
  );
}
