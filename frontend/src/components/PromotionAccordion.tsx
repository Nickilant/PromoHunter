import { useState } from 'react';

import type { PromotionWithStatuses, RestaurantShort } from '../types';
import { formatDate, timeAgo } from '../utils/time';
import StatusBadge from './StatusBadge';

interface Props {
  restaurant: RestaurantShort;
  promotion: PromotionWithStatuses;
  onReport: (restaurant: RestaurantShort, promotion: PromotionWithStatuses) => void;
  defaultOpen?: boolean;
}

export default function PromotionAccordion({
  restaurant,
  promotion,
  onReport,
  defaultOpen = false,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="promo-block">
      <button className="promo-toggle" onClick={() => setOpen(!open)}>
        <div>
          <div className="promo-title">{promotion.title}</div>
          {promotion.ends_at && (
            <div className="promo-sub">до {formatDate(promotion.ends_at)}</div>
          )}
        </div>
        <span className={`chevron ${open ? 'open' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="promo-body">
          {promotion.description && (
            <div className="promo-desc">{promotion.description}</div>
          )}
          {promotion.items.map((item) => {
            const updated = timeAgo(item.last_report_at);
            const total = item.on_site_count + item.delivery_count;
            const parts: string[] = [];
            if (updated) parts.push(`обновлено ${updated}`);
            if (total > 0 && item.delivery_count > 0) {
              parts.push(`${item.on_site_count} с точки · ${item.delivery_count} доставка`);
            }
            return (
              <div className="item-row" key={item.id}>
                <span className="item-name">{item.name}</span>
                <span className="item-meta">
                  <StatusBadge status={item.status} />
                  {parts.length > 0 && (
                    <span className="updated">{parts.join(' · ')}</span>
                  )}
                </span>
              </div>
            );
          })}
          <button
            className="btn btn-primary btn-block"
            onClick={() => onReport(restaurant, promotion)}
          >
            Отметить наличие
          </button>
        </div>
      )}
    </div>
  );
}
