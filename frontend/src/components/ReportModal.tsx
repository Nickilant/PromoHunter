import { useState } from 'react';

import { api, ApiError } from '../api/client';
import type { PromotionWithStatuses, ReportChannel, RestaurantShort } from '../types';
import { useToast } from './Toast';
import Icon from './Icon';
import { useDismiss } from '../hooks/useDismiss';

type Choice = 'yes' | 'no' | 'skip';

interface Props {
  restaurant: RestaurantShort;
  promotion: PromotionWithStatuses;
  onClose: () => void;
  onReported: () => void;
}

export default function ReportModal({ restaurant, promotion, onClose, onReported }: Props) {
  const [choices, setChoices] = useState<Record<number, Choice>>(() =>
    Object.fromEntries(promotion.items.map((i) => [i.id, 'skip'])),
  );
  const [channel, setChannel] = useState<ReportChannel>('on_site');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const toast = useToast();

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  const marked = promotion.items.filter((i) => choices[i.id] !== 'skip');

  const submit = async () => {
    setError(null);
    setSending(true);
    try {
      await api.post('/reports', {
        restaurant_id: restaurant.id,
        promotion_id: promotion.id,
        channel,
        items: marked.map((i) => ({
          promotion_item_id: i.id,
          is_available: choices[i.id] === 'yes',
        })),
      });
      toast('Спасибо! Отчёт учтён');
      onReported();
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError('Чтобы отмечать наличие, войдите в аккаунт');
      } else {
        setError(e instanceof Error ? e.message : 'Не получилось отправить отчёт');
      }
    } finally {
      setSending(false);
    }
  };

  const setChoice = (itemId: number, choice: Choice) =>
    setChoices((prev) => ({ ...prev, [itemId]: choice }));

  return (
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
            <h2>Отметить наличие</h2>
            <div className="subtitle">
              {restaurant.title || restaurant.brand.name} · {promotion.title}
            </div>
          </div>
          <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
            <Icon name="close" size={20} />
          </button>
        </div>
        <div className="modal-body">
          <div className="channel-toggle">
            <button
              className={channel === 'on_site' ? 'on' : ''}
              onClick={() => setChannel('on_site')}
            >
              <Icon name="store" size={18} />
              Я на точке
            </button>
            <button
              className={channel === 'delivery' ? 'on' : ''}
              onClick={() => setChannel('delivery')}
            >
              <Icon name="truck" size={18} />
              Заказывал доставку
            </button>
          </div>
          {channel === 'delivery' && (
            <div className="channel-hint">
              Убедитесь, что заказ готовила именно эта точка — адрес ресторана
              указан в чеке заказа: {restaurant.address}
            </div>
          )}
          {promotion.items.map((item) => (
            <div className="report-item" key={item.id}>
              <div className="name">{item.name}</div>
              <div className="tri-toggle">
                <button
                  className={choices[item.id] === 'yes' ? 'on-yes' : ''}
                  onClick={() => setChoice(item.id, 'yes')}
                >
                  Есть
                </button>
                <button
                  className={choices[item.id] === 'no' ? 'on-no' : ''}
                  onClick={() => setChoice(item.id, 'no')}
                >
                  Нет
                </button>
                <button
                  className={choices[item.id] === 'skip' ? 'on-skip' : ''}
                  onClick={() => setChoice(item.id, 'skip')}
                >
                  Не смотрел
                </button>
              </div>
            </div>
          ))}
          {error && <div className="form-error">{error}</div>}
        </div>
        <div className="modal-footer">
          <button
            className={`btn btn-primary btn-block${sending ? ' is-busy' : ''}`}
            disabled={marked.length === 0 || sending}
            onClick={submit}
            aria-busy={sending}
          >
            {sending && <span className="spinner" />}
            {sending ? 'Отправляем…' : `Отправить${marked.length ? ` (${marked.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}
