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
            return (
              <div className="item-row" key={item.id}>
                <span className="item-name">{item.name}</span>
                <span className="item-meta">
                  <StatusBadge status={item.status} />
                  {updated && <span className="updated">обновлено {updated}</span>}
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
