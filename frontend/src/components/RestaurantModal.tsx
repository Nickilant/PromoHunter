import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useSubscriptions } from '../hooks/useSubscriptions';
import type {
  PromotionWithStatuses,
  RestaurantDetail,
  RestaurantShort,
} from '../types';
import CapturePanel from './CapturePanel';
import Overlay from './Overlay';
import PromoCodesModal from './PromoCodesModal';
import PromotionAccordion from './PromotionAccordion';
import ReportModal from './ReportModal';
import Icon from './Icon';
import { useDismiss } from '../hooks/useDismiss';

interface Props {
  restaurantId: number;
  onClose: () => void;
}

// Модалка точки: адрес + акции сети со статусами и кнопкой отчёта
export default function RestaurantModal({ restaurantId, onClose }: Props) {
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [reportTarget, setReportTarget] = useState<{
    restaurant: RestaurantShort;
    promotion: PromotionWithStatuses;
  } | null>(null);
  const [codesOpen, setCodesOpen] = useState(false);
  const { user } = useAuth();
  const { isSubscribedToRestaurant, toggleRestaurant } = useSubscriptions();
  const navigate = useNavigate();

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  const load = useCallback(() => {
    api.get<RestaurantDetail>(`/restaurants/${restaurantId}`).then(setDetail).catch(() => {});
  }, [restaurantId]);

  useEffect(load, [load]);

  const openReport = (restaurant: RestaurantShort, promotion: PromotionWithStatuses) => {
    if (!user) {
      navigate('/login');
      return;
    }
    setReportTarget({ restaurant, promotion });
  };

  return (
    <>
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
            {detail ? (
              <div className="rest-card-head" style={{ padding: 0 }}>
                <span className="brand-chip" style={{ background: detail.brand.color }}>
                  {detail.brand.name}
                </span>
                <div className="rest-card-titles">
                  {detail.title && <div className="title">{detail.title}</div>}
                  <div className="address">
                    {detail.address}
                    {/* Карточку открыли из списка — где это на карте, неочевидно.
                        С самой карты сюда не попадают: там своя шторка */}
                    <button
                      className="show-on-map"
                      onClick={() => navigate(`/map?point=${restaurantId}`)}
                    >
                      <Icon name="map" size={13} strokeWidth={2} />
                      На карте
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rest-card-head" style={{ padding: 0, flex: 1 }}>
                <span
                  className="skeleton on-surface"
                  style={{ width: 96, height: 24, borderRadius: 999 }}
                />
                <span
                  className="skeleton on-surface"
                  style={{ width: '45%', height: 16, borderRadius: 8 }}
                />
              </div>
            )}
            {/* Промокоды сети — рядом с колокольчиком: человек уже выбрал
                точку и вот-вот сделает заказ */}
            {detail && (
              <button
                className="head-bell"
                onClick={() => setCodesOpen(true)}
                aria-label="Промокоды сети"
                title="Промокоды сети"
              >
                <Icon name="ticket" size={19} />
              </button>
            )}
            {/* Колокольчик — в строке с названием, а не отдельной полосой */}
            {detail && (
              <button
                className={`head-bell${
                  isSubscribedToRestaurant(restaurantId) ? ' on' : ''
                }`}
                onClick={() => {
                  if (!user) {
                    navigate('/login');
                    return;
                  }
                  toggleRestaurant(restaurantId);
                }}
                aria-pressed={isSubscribedToRestaurant(restaurantId)}
                aria-label={
                  isSubscribedToRestaurant(restaurantId)
                    ? 'Отписаться от новостей точки'
                    : 'Подписаться на новости точки'
                }
                title={
                  isSubscribedToRestaurant(restaurantId)
                    ? 'Отписаться от новостей точки'
                    : 'Подписаться на новости точки'
                }
              >
                <Icon
                  name={isSubscribedToRestaurant(restaurantId) ? 'bell' : 'bellOff'}
                  size={19}
                />
              </button>
            )}
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          </div>
          <CapturePanel restaurantId={restaurantId} />
          <div className="modal-body" style={{ paddingBottom: 16 }}>
            {detail && detail.promotions.length === 0 && (
              <div className="empty-state">Сейчас в этой точке нет действующих акций</div>
            )}
            {detail?.promotions.map((promo) => (
              <div className="promo-in-modal" key={promo.id}>
                <PromotionAccordion
                  restaurant={detail}
                  promotion={promo}
                  onReport={openReport}
                  defaultOpen={detail.promotions.length === 1}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
      </Overlay>

      {codesOpen && detail && (
        <PromoCodesModal brand={detail.brand} onClose={() => setCodesOpen(false)} />
      )}

      {/* Отметка наличия — свой оверлей со своим порталом, вкладывать её
          в портал карточки нельзя (см. комментарий в Overlay.tsx) */}
      {reportTarget && (
        <ReportModal
          restaurant={reportTarget.restaurant}
          promotion={reportTarget.promotion}
          onClose={() => setReportTarget(null)}
          onReported={load}
        />
      )}
    </>
  );
}
