import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import MapPickerWithSearch from '../components/MapPickerWithSearch';
import { useCity } from '../hooks/useCity';
import type { Brand } from '../types';
import Icon from '../components/Icon';

export default function SuggestRestaurantPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState('');
  const { city: sessionCity } = useCity();
  const [city, setCity] = useState(sessionCity ?? '');
  const [address, setAddress] = useState('');
  const [title, setTitle] = useState('');
  const [comment, setComment] = useState('');
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<Brand[]>('/brands').then(setBrands).catch(() => {});
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (lat === null || lng === null) {
      setError('Отметьте точку на карте: найдите адрес и тапните по месту');
      return;
    }
    setError(null);
    setSending(true);
    try {
      await api.post('/restaurant-suggestions', {
        brand_id: Number(brandId),
        city,
        address,
        title: title || null,
        comment: comment || null,
        lat,
        lng,
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
          <div>Проверим и добавим точку на карту. Статус — в профиле.</div>
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
        <h1>Добавить ресторан</h1>
      </div>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="field">
          <label>Сеть</label>
          <select value={brandId} onChange={(e) => setBrandId(e.target.value)} required>
            <option value="" disabled>
              Выберите сеть…
            </option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <div className="hint">
            Нет нужной сети? Заявите её акцию — сеть добавит модератор
          </div>
        </div>
        <div className="field">
          <label>Город</label>
          <input value={city} onChange={(e) => setCity(e.target.value)} required />
        </div>
        <div className="field">
          <label>Адрес</label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Невский пр., 55"
            required
          />
        </div>
        <div className="field">
          <label>Место на карте</label>
          <MapPickerWithSearch
            lat={lat}
            lng={lng}
            city={city || null}
            onPick={(la, ln) => {
              setLat(la);
              setLng(ln);
              setError(null);
            }}
          />
          {lat !== null && lng !== null && (
            <div className="hint">
              Точка отмечена: {lat.toFixed(5)}, {lng.toFixed(5)}
            </div>
          )}
        </div>
        <div className="field">
          <label>Название точки (необязательно)</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="ТЦ Галерея, 2 этаж"
          />
        </div>
        <div className="field">
          <label>Комментарий (необязательно)</label>
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Как найти, этаж, ориентиры"
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={sending}>
          {sending ? 'Отправляем…' : 'Отправить на модерацию'}
        </button>
      </form>
    </div>
  );
}
