import { FormEvent, useEffect, useState } from 'react';

import { api, ApiError } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import type { BrandShort, PromoCode } from '../types';
import { useDismiss } from '../hooks/useDismiss';
import Icon from './Icon';
import Overlay from './Overlay';
import { useToast } from './Toast';

interface Props {
  brand: BrandShort;
  onClose: () => void;
}

/**
 * Промокоды сети. Отдельная от акций сущность: код — это не предмет на полке
 * конкретной точки, а информация, которая работает у всей сети.
 *
 * Тап по строке выбирает код и кладёт его в буфер обмена. Подтверждение —
 * только явными кнопками: скопировать могли и не дойти до кассы.
 */
export default function PromoCodesModal({ brand, onClose }: Props) {
  const [codes, setCodes] = useState<PromoCode[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [isGlobal, setIsGlobal] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { user } = useAuth();
  const { city } = useCity();
  const toast = useToast();

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  const load = () => {
    const params = new URLSearchParams({ brand_id: String(brand.id) });
    if (city) params.set('city', city);
    api
      .get<PromoCode[]>(`/promo-codes?${params}`)
      .then(setCodes)
      .catch(() => setCodes([]));
  };

  useEffect(load, [brand.id, city]);

  const pick = async (item: PromoCode) => {
    setSelected(item.id);
    try {
      await navigator.clipboard.writeText(item.code);
      toast(`Промокод ${item.code} скопирован`);
    } catch {
      // Буфер недоступен (нет разрешения или старый браузер) — код виден
      // на экране, перепечатать можно и руками
    }
  };

  const vote = async (item: PromoCode, worked: boolean) => {
    if (!user) {
      setError('Чтобы отмечать промокоды, войдите в аккаунт');
      return;
    }
    setError(null);
    try {
      await api.post(`/promo-codes/${item.id}/vote`, { worked });
      toast(worked ? 'Спасибо, отметили' : 'Спасибо, уберём его из списка');
      setSelected(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не получилось отметить');
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await api.post('/promo-codes', {
        brand_id: brand.id,
        code,
        description,
        is_global: isGlobal,
        city,
      });
      setCode('');
      setDescription('');
      setIsGlobal(true);
      setAdding(false);
      load();
      toast('Промокод добавлен');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не получилось добавить');
    } finally {
      setSending(false);
    }
  };

  return (
    <Overlay>
      <div
        className={`modal-overlay${closing ? ' closing' : ''}`}
        onClick={dismiss}
        onAnimationEnd={onAnimationEnd}
      >
        <div
          className={`modal${closing ? ' closing' : ''}`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-head">
            <div>
              <h2>Промокоды</h2>
              {/* Коды сетевые, а не точечные — говорим это прямо, иначе
                  будет непонятно, почему список одинаковый на всех адресах */}
              <div className="subtitle">
                {brand.name} · работают во всей сети
              </div>
            </div>
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          </div>

          <div className="modal-body">
            {codes === null && (
              <div className="skeleton-list" aria-busy="true">
                {[0, 1].map((i) => (
                  <div className="skeleton" style={{ height: 64, borderRadius: 12 }} key={i} />
                ))}
              </div>
            )}

            {codes !== null && codes.length === 0 && !adding && (
              <div className="empty-state">
                <div className="big">
                  <Icon name="ticket" size={44} strokeWidth={1.4} />
                </div>
                <div>Рабочих промокодов этой сети пока нет</div>
              </div>
            )}

            {codes?.map((item) => (
              <div
                className={`promo-code${selected === item.id ? ' selected' : ''}`}
                key={item.id}
              >
                <button className="promo-code-main" onClick={() => pick(item)}>
                  <span className="promo-code-value">{item.code}</span>
                  <span className="promo-code-desc">{item.description}</span>
                  <span className="promo-code-meta muted">
                    {item.is_global ? 'вся сеть' : item.cities.join(', ')}
                    {item.confirmations > 0 && ` · подтверждали ${item.confirmations}`}
                    {item.author_name && ` · принёс ${item.author_name}`}
                  </span>
                </button>
                {selected === item.id && (
                  <div className="promo-code-actions">
                    <button className="btn btn-primary btn-small" onClick={() => vote(item, true)}>
                      <Icon name="check" size={15} strokeWidth={2.4} />
                      Сработал
                    </button>
                    <button className="btn btn-ghost btn-small" onClick={() => vote(item, false)}>
                      <Icon name="close" size={15} strokeWidth={2.4} />
                      Не сработал
                    </button>
                  </div>
                )}
              </div>
            ))}

            {adding && (
              <form onSubmit={submit} className="promo-code-form">
                <div className="field">
                  <label htmlFor="pc-code">Промокод</label>
                  <input
                    id="pc-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="SALE20"
                    autoCapitalize="characters"
                    maxLength={64}
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor="pc-desc">Что даёт</label>
                  <input
                    id="pc-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Скидка 20% на заказ от 500 ₽"
                    maxLength={200}
                    required
                  />
                </div>
                <div className="field">
                  <label>Где работает</label>
                  <div className="scope-choice">
                    <button
                      type="button"
                      className={isGlobal ? 'on' : ''}
                      onClick={() => setIsGlobal(true)}
                    >
                      Везде
                    </button>
                    <button
                      type="button"
                      className={!isGlobal ? 'on' : ''}
                      onClick={() => setIsGlobal(false)}
                      disabled={!city}
                    >
                      Только {city ?? 'мой город'}
                    </button>
                  </div>
                </div>
                {error && <div className="form-error">{error}</div>}
                <div className="promo-code-form-actions">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setAdding(false);
                      setError(null);
                    }}
                  >
                    Отмена
                  </button>
                  <button className="btn btn-primary" disabled={sending}>
                    {sending ? 'Добавляем…' : 'Добавить'}
                  </button>
                </div>
              </form>
            )}

            {!adding && error && <div className="form-error">{error}</div>}
          </div>

          {!adding && (
            <div className="modal-footer">
              <button
                className="btn btn-ghost btn-block"
                onClick={() => {
                  if (!user) {
                    setError('Чтобы добавить промокод, войдите в аккаунт');
                    return;
                  }
                  setError(null);
                  setAdding(true);
                }}
              >
                <Icon name="plus" size={17} strokeWidth={2.2} />
                Добавить новый промокод
              </button>
            </div>
          )}
        </div>
      </div>
    </Overlay>
  );
}
