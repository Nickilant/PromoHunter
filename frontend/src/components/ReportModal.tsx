import { useState } from 'react';

import { api, ApiError } from '../api/client';
import type {
  PromotionWithStatuses,
  Report,
  ReportChannel,
  RestaurantShort,
} from '../types';
import { useToast } from './Toast';
import Icon from './Icon';
import ReceiptScanner from './ReceiptScanner';
import { useDismiss } from '../hooks/useDismiss';
import { useGame } from '../hooks/useGame';
import { FACTION_TITLE } from '../utils/faction';

type Choice = 'yes' | 'no' | 'skip';

interface Props {
  restaurant: RestaurantShort;
  promotion: PromotionWithStatuses;
  onClose: () => void;
  onReported: () => void;
}

/** Координаты нужны только для чека: чек принимаем лишь рядом с точкой */
function currentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Геолокация недоступна на этом устройстве'));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      timeout: 12000,
      enableHighAccuracy: true,
    });
  });
}

export default function ReportModal({ restaurant, promotion, onClose, onReported }: Props) {
  const [choices, setChoices] = useState<Record<number, Choice>>(() =>
    Object.fromEntries(promotion.items.map((i) => [i.id, 'skip'])),
  );
  const [channel, setChannel] = useState<ReportChannel>('on_site');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const toast = useToast();
  const { enabled: gameEnabled, faction, config, refreshPoints } = useGame();

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  const marked = promotion.items.filter((i) => choices[i.id] !== 'skip');
  const hasYes = marked.some((i) => choices[i.id] === 'yes');
  // Захват возможен только «на точке» и только когда товар отмечен как есть
  const canCapture = gameEnabled && faction !== null && channel === 'on_site';

  const attachReceipt = async (raw: string) => {
    setError(null);
    setLocating(true);
    try {
      const position = await currentPosition();
      setCoords({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      });
      setReceipt(raw);
    } catch {
      setError(
        'Нужно разрешить доступ к геолокации — чек засчитываем только на точке',
      );
    } finally {
      setLocating(false);
    }
  };

  const submit = async () => {
    setError(null);
    setSending(true);
    try {
      const report = await api.post<Report>('/reports', {
        restaurant_id: restaurant.id,
        promotion_id: promotion.id,
        channel,
        items: marked.map((i) => ({
          promotion_item_id: i.id,
          is_available: choices[i.id] === 'yes',
        })),
        ...(receipt ? { receipt_qr: receipt, ...coords } : {}),
      });
      const capture = report.capture;
      if (capture) {
        refreshPoints();
        if (capture.captured) {
          toast(`Точка взята! ${FACTION_TITLE[capture.faction]} держат её`);
        } else if (capture.defended) {
          toast('Атака отбита — точка осталась за вами');
        } else {
          toast(`Чек принят: +${capture.points} очков, сила +${capture.strength}`);
        }
      } else {
        toast('Спасибо! Отчёт учтён');
      }
      onReported();
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError('Чтобы отмечать наличие, войдите в аккаунт');
      } else {
        setError(e instanceof Error ? e.message : 'Не получилось отправить отчёт');
      }
      // Чек одноразовый: если он не прошёл, второй раз его отправлять нечего
      setReceipt(null);
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
          {canCapture && (
            <div className="capture-attach">
              <div className="capture-attach-head">
                <Icon name="swords" size={17} strokeWidth={2} />
                <span>Захват точки</span>
                <span className={`faction-chip ${faction} small`}>
                  {FACTION_TITLE[faction!]}
                </span>
              </div>
              {receipt === null ? (
                <>
                  <div className="capture-attach-hint">
                    {hasYes
                      ? `Приложите чек с этой покупки — от ${
                          config?.min_sum_rubles ?? 50
                        } ₽ и не старше ${
                          config?.receipt_max_age_minutes ?? 15
                        } мин. Только чек добавляет силу вашей стороне.`
                      : 'Сначала отметьте «Есть» у того, что купили, — захват идёт только по наличию.'}
                  </div>
                  {hasYes && (
                    <>
                      <ReceiptScanner onScanned={attachReceipt} disabled={locating} />
                      {locating && (
                        <div className="capture-attach-hint">
                          <span className="spinner" /> Определяем, что вы на точке…
                        </div>
                      )}
                    </>
                  )}
                </>
              ) : (
                <div className="capture-attached">
                  <Icon name="checkCircle" size={18} className="ico-yes" />
                  <span>Чек прикреплён</span>
                  <button
                    className="btn btn-ghost btn-small"
                    onClick={() => {
                      setReceipt(null);
                      setCoords(null);
                    }}
                  >
                    Убрать
                  </button>
                </div>
              )}
            </div>
          )}
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
            {sending
              ? 'Отправляем…'
              : receipt
                ? 'Отправить и захватывать'
                : `Отправить${marked.length ? ` (${marked.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}
