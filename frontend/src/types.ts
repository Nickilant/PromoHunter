export type Role = 'user' | 'admin';

export interface User {
  id: number;
  phone: string;
  is_phone_verified: boolean;
  display_name: string;
  city: string | null;
  role: Role;
  is_blocked: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface BrandShort {
  id: number;
  name: string;
  color: string;
}

export interface Brand extends BrandShort {
  slug: string;
  logo_url: string | null;
}

export interface AdminBrand extends Brand {
  created_at: string;
  restaurants_count: number;
}

export interface RestaurantShort {
  id: number;
  brand: BrandShort;
  title: string | null;
  city: string;
  address: string;
  lat: number;
  lng: number;
}

export interface RestaurantListItem extends RestaurantShort {
  active_promotions_count: number;
  last_report_at: string | null;
}

export interface CityInfo {
  name: string;
  restaurants_count: number;
}

export interface CatalogPromo {
  id: number;
  title: string;
}

export interface CatalogBrand {
  id: number;
  name: string;
  color: string;
  logo_url: string | null;
  restaurants_count: number;
  promotions: CatalogPromo[];
}

export interface AdminRestaurant extends RestaurantShort {
  is_active: boolean;
  created_at: string;
}

export type ItemStatus =
  | 'available'
  | 'unavailable'
  | 'maybe_gone'
  | 'maybe_appeared'
  | 'disputed'
  | 'unknown';

export type ReportChannel = 'on_site' | 'delivery';

export interface ItemWithStatus {
  id: number;
  name: string;
  status: ItemStatus;
  yes_count: number;
  no_count: number;
  on_site_count: number;
  delivery_count: number;
  last_report_at: string | null;
}

export interface PromotionWithStatuses {
  id: number;
  title: string;
  description: string | null;
  starts_at: string | null;
  ends_at: string | null;
  items: ItemWithStatus[];
}

export interface FeedEntry {
  restaurant: RestaurantShort;
  promotions: PromotionWithStatuses[];
}

export interface RestaurantDetail extends RestaurantShort {
  promotions: PromotionWithStatuses[];
}

export interface ReportItemOut {
  promotion_item_id: number;
  name: string;
  is_available: boolean;
}

export interface Report {
  id: number;
  restaurant: RestaurantShort;
  promotion_title: string;
  items: ReportItemOut[];
  created_at: string;
}

export type SuggestionStatus = 'pending' | 'approved' | 'rejected';

export interface Suggestion {
  id: number;
  brand_id: number | null;
  brand_name_raw: string | null;
  restaurant_id: number | null;
  title: string;
  description: string | null;
  items_raw: string;
  status: SuggestionStatus;
  moderator_comment: string | null;
  created_promotion_id: number | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface AdminSuggestion extends Suggestion {
  user: User;
  restaurant: RestaurantShort | null;
}

export interface SuggestionGroup {
  brand_id: number | null;
  brand_name: string;
  brand_color: string | null;
  suggestions: AdminSuggestion[];
}

export interface RestaurantSuggestion {
  id: number;
  brand: BrandShort;
  title: string | null;
  city: string;
  address: string;
  lat: number;
  lng: number;
  comment: string | null;
  status: SuggestionStatus;
  moderator_comment: string | null;
  created_restaurant_id: number | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface AdminRestaurantSuggestion extends RestaurantSuggestion {
  user: User;
}

export interface RestaurantSuggestionGroup {
  brand_id: number;
  brand_name: string;
  brand_color: string;
  suggestions: AdminRestaurantSuggestion[];
}

export interface PromotionItemAdmin {
  id: number;
  name: string;
  sort_order: number;
}

export interface AdminPromotion {
  id: number;
  brand: BrandShort;
  title: string;
  description: string | null;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  created_at: string;
  items: PromotionItemAdmin[];
}

export interface AdminUser extends User {
  reports_count: number;
}

// --- рейтинг ---

export type RatingPeriod = 'month' | 'year';

export interface RatingEntry {
  user_id: number;
  display_name: string;
  points: number;
  reports_count: number;
  pioneers_count: number;
  position: number;
}

export interface RatingResponse {
  entries: RatingEntry[];
  me: { position: number | null; points: number } | null;
}

export interface RatingCategory {
  type: string;
  count: number;
  points: number;
}

export interface RatingEventItem {
  type: string;
  points: number;
  city: string | null;
  context: string | null;
  created_at: string;
}

export interface RatingCard {
  user_id: number;
  display_name: string;
  total_points: number;
  categories: RatingCategory[];
  events: RatingEventItem[] | null;
}
