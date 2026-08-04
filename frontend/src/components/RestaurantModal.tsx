import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useSubscriptions } from '../hooks/useSubscriptions';
import type {
  Brand,
  PromotionWithStatuses,
  RestaurantDetail,
  RestaurantShort,
} from '../types';
import CapturePanel from './CapturePanel';
import DataIssueModal from './DataIssueModal';
import Overlay from './Overlay';
import PromoCodesModal from './PromoCodesModal';
import PromotionAccordion from './PromotionAccordion';
import ReportModal from './ReportModal';
import RestaurantHistoryModal from './RestaurantHistoryModal';
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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [issueOpen, setIssueOpen] = useState(false);
  const [brandLogoUrl, setBrandLogoUrl] = useState<string | null>(null);
  const { user } = useAuth();
  const { isSubscribedToRestaurant, toggleRestaurant } = useSubscriptions();
  const navigate = useNavigate();

  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  const load = useCallback(() => {
    api.get<RestaurantDetail>(`/restaurants/${restaurantId}`).then(setDetail).catch(() => {});
  }, [restaurantId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!detail) return;
    if (detail.brand.logo_url) {
      setBrandLogoUrl(detail.brand.logo_url);
      return;
    }

    let cancelled = false;
    api.get<Brand[]>('/brands').then((brands) => {
      if (cancelled) return;
      setBrandLogoUrl(
        brands.find((brand) => brand.id === detail.brand.id)?.logo_url ?? null,
      );
    }).catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [detail]);

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
          <div className="modal-head restaurant-modal-head">
            {detail ? (
              <div className="restaurant-modal-identity">
                {brandLogoUrl ? (
                  <img
                    className="restaurant-modal-logo"
                    src={brandLogoUrl}
                    alt={detail.brand.name}
                  />
                ) : (
                  <span className="brand-chip" style={{ background: detail.brand.color }}>
                    {detail.brand.name}
                  </span>
                )}
                <div className="restaurant-modal-location">
                  <div className="restaurant-modal-address">{detail.address}</div>
                  {detail.title && <div className="restaurant-modal-title">{detail.title}</div>}
                </div>
              </div>
            ) : (
              <div className="restaurant-modal-identity">
                <span
                  className="skeleton on-surface restaurant-modal-logo-skeleton"
                />
                <span
                  className="skeleton on-surface restaurant-modal-address-skeleton"
                />
              </div>
            )}
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
            {detail && <div className="restaurant-modal-actions">
              <button onClick={() => navigate(`/map?point=${restaurantId}`)}>
                <Icon name="map" size={18} />
                <span>На карте</span>
              </button>
              <button onClick={() => setHistoryOpen(true)}>
                <Icon name="chart" size={18} />
                <span>Сводка</span>
              </button>
              <button
                onClick={() => setCodesOpen(true)}
              >
                <Icon name="ticket" size={18} />
                <span>Промокоды</span>
              </button>
              <button
                className={isSubscribedToRestaurant(restaurantId) ? 'on' : ''}
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
              >
                <Icon
                  name={isSubscribedToRestaurant(restaurantId) ? 'bell' : 'bellOff'}
                  size={18}
                />
                <span>{isSubscribedToRestaurant(restaurantId) ? 'Подписан' : 'Подписаться'}</span>
              </button>
            </div>}
          </div>
          <div className="modal-body restaurant-modal-scroll" style={{ paddingBottom: 16 }}>
            <CapturePanel restaurantId={restaurantId} />
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
            {detail && <button className="data-issue-link data-issue-link-bottom" onClick={() => {
              if (!user) { navigate('/login'); return; }
              setIssueOpen(true);
            }}><Icon name="alert" size={16} />Сообщить об ошибке в данных</button>}
          </div>
        </div>
      </div>
      </Overlay>

      {codesOpen && detail && (
        <PromoCodesModal brand={detail.brand} onClose={() => setCodesOpen(false)} />
      )}
      {historyOpen && detail && <RestaurantHistoryModal restaurant={detail} onClose={() => setHistoryOpen(false)} />}
      {issueOpen && detail && <DataIssueModal restaurant={detail} onClose={() => setIssueOpen(false)} />}

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
