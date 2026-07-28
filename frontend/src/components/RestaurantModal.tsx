import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type {
  PromotionWithStatuses,
  RestaurantDetail,
  RestaurantShort,
} from '../types';
import PromotionAccordion from './PromotionAccordion';
import ReportModal from './ReportModal';

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
  const { user } = useAuth();
  const navigate = useNavigate();

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
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-head">
            {detail ? (
              <div className="rest-card-head" style={{ padding: 0 }}>
                <span className="brand-chip" style={{ background: detail.brand.color }}>
                  {detail.brand.name}
                </span>
                <div className="rest-card-titles">
                  {detail.title && <div className="title">{detail.title}</div>}
                  <div className="address">{detail.address}</div>
                </div>
              </div>
            ) : (
              <div className="subtitle">Загружаем…</div>
            )}
            <button className="modal-close" onClick={onClose} aria-label="Закрыть">
              ✕
            </button>
          </div>
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
