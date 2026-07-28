import type { FeedEntry, PromotionWithStatuses, RestaurantShort } from '../types';
import PromotionAccordion from './PromotionAccordion';

interface Props {
  entry: FeedEntry;
  onReport: (restaurant: RestaurantShort, promotion: PromotionWithStatuses) => void;
}

export default function RestaurantCard({ entry, onReport }: Props) {
  const { restaurant, promotions } = entry;
  return (
    <div className="rest-card">
      <div className="rest-card-head">
        <span className="brand-chip" style={{ background: restaurant.brand.color }}>
          {restaurant.brand.name}
        </span>
        <div className="rest-card-titles">
          {restaurant.title && <div className="title">{restaurant.title}</div>}
          <div className="address">{restaurant.address}</div>
        </div>
      </div>
      {promotions.map((promo) => (
        <PromotionAccordion
          key={promo.id}
          restaurant={restaurant}
          promotion={promo}
          onReport={onReport}
        />
      ))}
    </div>
  );
}
