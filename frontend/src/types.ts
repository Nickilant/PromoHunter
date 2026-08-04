export type Role = 'user' | 'moderator' | 'admin';

/** Кто я в админке: глобальный админ или модератор своих городов */
export interface StaffScope {
  role: Role;
  is_global: boolean;
  cities: string[];
}

/** Как читать список городов акции */
export type PromotionCityMode = 'exclude' | 'include';

export interface PromotionScope {
  mode: PromotionCityMode;
  cities: string[];
}

export type Faction = 'green' | 'purple';

export interface User {
  id: number;
  phone: string;
  is_phone_verified: boolean;
  display_name: string;
  city: string | null;
  has_telegram: boolean;
  has_password: boolean;
  role: Role;
  is_blocked: boolean;
  game_mode: boolean;
  game_asked: boolean;
  faction: Faction | null;
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
  logo_url?: string | null;
}

export interface Brand extends BrandShort {
  slug: string;
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

export interface AdminCity {
  id: number;
  name: string;
  is_active: boolean;
  restaurants_count: number;
}

export interface CityBulkResult {
  added: string[];
  skipped: string[];
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

export interface CaptureResult {
  strength: number;
  points: number;
  faction: Faction;
  owner: Faction | null;
  captured: boolean;
  defended: boolean;
  refuted_denials: number;
}

export interface Report {
  id: number;
  restaurant: RestaurantShort;
  promotion_title: string;
  items: ReportItemOut[];
  is_receipt_verified: boolean;
  capture: CaptureResult | null;
  created_at: string;
}

export interface HistoryItem {
  promotion_title: string;
  item_name: string;
  reports_count: number;
  available_count: number;
  availability_percent: number;
  last_available_at: string | null;
  last_unavailable_at: string | null;
}

export interface RestaurantHistory {
  days: number;
  reports_count: number;
  contributors_count: number;
  last_report_at: string | null;
  items: HistoryItem[];
}

export type IssueStatus = 'pending' | 'resolved' | 'rejected';

export interface DataIssue {
  id: number;
  restaurant: RestaurantShort;
  promotion_id: number | null;
  promotion_title: string | null;
  type: string;
  details: string;
  status: IssueStatus;
  moderator_comment: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface AdminDataIssue extends DataIssue {
  user: User;
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
  city: string | null;
  status: SuggestionStatus;
  moderator_comment: string | null;
  created_promotion_id: number | null;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
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
  reviewed_by_name: string | null;
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
  city_mode: PromotionCityMode;
  scope_cities: string[];
  scope_label: string;
  /** Может ли текущий сотрудник править саму акцию, а не только свой город */
  can_edit: boolean;
}

export interface AdminUser extends User {
  reports_count: number;
  moderator_cities: string[];
}

export interface TelegramInfo {
  enabled: boolean;
  bot_username: string | null;
}

// --- подписки ---

export interface PromotionShort {
  id: number;
  title: string;
  brand: BrandShort;
}

export interface Subscription {
  id: number;
  restaurant: RestaurantShort | null;
  promotion: PromotionShort | null;
  created_at: string;
}

// --- рейтинг ---

export type RatingPeriod = 'month' | 'year';

/** all — весь город, faction — только своя сторона */
export type RatingScope = 'all' | 'faction';

export interface RatingEntry {
  user_id: number;
  display_name: string;
  points: number;
  reports_count: number;
  pioneers_count: number;
  position: number;
}

/** Своя строка приходит всегда; position = null — очков ещё нет */
export interface RatingMe extends Omit<RatingEntry, 'position'> {
  position: number | null;
}

export interface RatingResponse {
  entries: RatingEntry[];
  total: number;
  me: RatingMe | null;
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

// --- игровой режим ---

export interface FactionInfo {
  key: Faction;
  title: string;
  members: number;
  share: number;
  join_blocked: boolean;
  underdog_bonus: number;
}

export interface GameMe {
  game_mode: boolean;
  asked: boolean;
  faction: Faction | null;
  can_switch_at: string | null;
}

export interface GameConfig {
  enabled: boolean;
  city: string | null;
  season: string;
  factions: FactionInfo[];
  me: GameMe | null;
  bar_seconds: number;
  min_sum_rubles: number;
  receipt_max_age_minutes: number;
  geo_radius_m: number;
}

export interface PointControl {
  restaurant_id: number;
  owner: Faction | null;
  green_score: number;
  purple_score: number;
  green_receipts: number;
  purple_receipts: number;
  green_progress: number;
  purple_progress: number;
  leader: Faction | null;
  under_attack: boolean;
  eta_seconds: number | null;
  is_active_now: boolean;
  truce_seconds: number | null;
  captured_at: string | null;
}

export interface PointControlDetail extends PointControl {
  my_receipts_today: number;
  my_strength_today: number;
  my_faction: Faction | null;
}

export interface FactionStanding {
  faction: Faction;
  title: string;
  points_held: number;
  held_share: number;
  captures: number;
  defends: number;
}

export interface GameStandings {
  city: string;
  season: string;
  points_total: number;
  neutral: number;
  standings: FactionStanding[];
}

// --- промокоды ---

export interface PromoCode {
  id: number;
  code: string;
  description: string;
  is_global: boolean;
  cities: string[];
  author_name: string | null;
  confirmations: number;
  expires_at: string;
  created_at: string;
  confirmed_by_me: boolean;
  is_mine: boolean;
}
