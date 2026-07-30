// Весь код Leaflet изолирован в этом компоненте,
// чтобы карту можно было заменить (например, на Яндекс.Карты), не трогая остальное.
import 'leaflet/dist/leaflet.css';

import { useEffect } from 'react';
import {
  CircleMarker,
  LayerGroup,
  MapContainer,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet';

import type { PointControl, RestaurantListItem } from '../types';
import { FACTION_HEX, formatEtaShort, NEUTRAL_HEX } from '../utils/faction';
import Icon from './Icon';

const DEFAULT_CENTER: [number, number] = [59.935, 30.325]; // Санкт-Петербург
const DEFAULT_ZOOM = 12;
const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
// Копирайт OSM обязателен по условиям бесплатных тайлов — оставляем его,
// но без префикса «Leaflet» и в максимально ненавязчивом виде (см. CSS)
const TILE_ATTRIBUTION =
  '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a>';

/** Убирает префикс «🇺🇦 Leaflet» из плашки атрибуции */
function CleanAttribution() {
  const map = useMap();
  useEffect(() => {
    map.attributionControl?.setPrefix('');
  }, [map]);
  return null;
}

export interface MapFocus {
  lat: number;
  lng: number;
  zoom?: number;
}

function LocateButton() {
  const map = useMap();
  const locate = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      // Ничего не отправляем на сервер — только центрируем карту
      map.flyTo([pos.coords.latitude, pos.coords.longitude], 15);
    });
  };
  return (
    <button
      className="locate-btn"
      style={{ zIndex: 1000 }}
      onClick={(e) => {
        e.stopPropagation();
        locate();
      }}
      aria-label="Найти меня"
      title="Найти меня"
    >
      <Icon name="locate" size={21} />
    </button>
  );
}

/** Центрирует карту на точке (поиск адреса) */
function FlyTo({ focus }: { focus: MapFocus | null }) {
  const map = useMap();
  useEffect(() => {
    if (focus) map.flyTo([focus.lat, focus.lng], focus.zoom ?? 16);
  }, [focus, map]);
  return null;
}

/** Вписывает в экран все маркеры города при их смене */
function FitToMarkers({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(',')).join(';');
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(points, { padding: [48, 48], maxZoom: 14 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

/**
 * Слой принадлежности точек — отдельная группа поверх тайлов и под маркерами
 * сетей: цветной ореол вокруг точки и подпись с таймером, если идёт битва.
 * Скрывается кнопкой, ничего не зная про остальную карту.
 */
function OwnershipLayer({
  restaurants,
  points,
}: {
  restaurants: RestaurantListItem[];
  points: Map<number, PointControl>;
}) {
  return (
    <LayerGroup>
      {restaurants.map((r) => {
        const point = points.get(r.id);
        if (!point) return null;
        const battle = point.leader !== null;
        if (point.owner === null && !battle) return null;
        const color = point.owner ? FACTION_HEX[point.owner] : NEUTRAL_HEX;
        const leaderColor = point.leader ? FACTION_HEX[point.leader] : color;
        return (
          <CircleMarker
            key={`own-${r.id}`}
            center={[r.lat, r.lng]}
            radius={battle ? 22 : 18}
            interactive={false}
            className={battle ? 'own-halo pulsing' : 'own-halo'}
            pathOptions={{
              color: leaderColor,
              weight: battle ? 3 : 2,
              opacity: battle ? 0.95 : 0.55,
              fillColor: color,
              fillOpacity: point.owner ? 0.22 : 0.1,
              dashArray: battle && point.owner ? '5 4' : undefined,
            }}
          >
            {battle && point.is_active_now && (
              <Tooltip
                permanent
                direction="top"
                offset={[0, -20]}
                className={`map-timer-tip ${point.leader}`}
              >
                {formatEtaShort(point.eta_seconds)}
              </Tooltip>
            )}
          </CircleMarker>
        );
      })}
    </LayerGroup>
  );
}

/** Кнопка скрытия слоя владения — рядом с «найти меня» */
function LayerToggle({
  visible,
  onToggle,
}: {
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      className={`layer-btn${visible ? ' on' : ''}`}
      style={{ zIndex: 1000 }}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      aria-pressed={visible}
      aria-label={visible ? 'Скрыть слой владения' : 'Показать слой владения'}
      title={visible ? 'Скрыть слой владения' : 'Показать слой владения'}
    >
      <Icon name="layers" size={20} />
    </button>
  );
}

interface RestaurantsMapProps {
  restaurants: RestaurantListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  focus: MapFocus | null;
  searchPoint: MapFocus | null;
  /** Игровой слой: пусто — карта ведёт себя как раньше */
  points?: Map<number, PointControl>;
  layerVisible?: boolean;
  onToggleLayer?: () => void;
}

export function RestaurantsMap({
  restaurants,
  selectedId,
  onSelect,
  focus,
  searchPoint,
  points,
  layerVisible = false,
  onToggleLayer,
}: RestaurantsMapProps) {
  return (
    <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} zoomControl={false}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      <CleanAttribution />
      <FitToMarkers points={restaurants.map((r) => [r.lat, r.lng])} />
      <FlyTo focus={focus} />
      {points && layerVisible && (
        <OwnershipLayer restaurants={restaurants} points={points} />
      )}
      {searchPoint && (
        <CircleMarker
          center={[searchPoint.lat, searchPoint.lng]}
          radius={9}
          pathOptions={{
            color: '#C98B6B',
            weight: 3,
            fillColor: '#fff',
            fillOpacity: 0.9,
          }}
        />
      )}
      {restaurants.map((r) => (
        <CircleMarker
          key={r.id}
          center={[r.lat, r.lng]}
          radius={selectedId === r.id ? 13 : 10}
          pathOptions={{
            color: '#fff',
            weight: 2,
            fillColor: r.brand.color,
            fillOpacity: 1,
          }}
          eventHandlers={{ click: () => onSelect(r.id) }}
        />
      ))}
      {points && onToggleLayer && (
        <LayerToggle visible={layerVisible} onToggle={onToggleLayer} />
      )}
      <LocateButton />
    </MapContainer>
  );
}

function ClickHandler({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click: (e) => onPick(e.latlng.lat, e.latlng.lng),
  });
  return null;
}

interface LocationPickerProps {
  lat: number | null;
  lng: number | null;
  onPick: (lat: number, lng: number) => void;
  /** Точка из поиска по адресу — карта подлетает к ней */
  focus?: MapFocus | null;
}

export function LocationPickerMap({ lat, lng, onPick, focus = null }: LocationPickerProps) {
  const hasPoint = lat !== null && lng !== null && !(lat === 0 && lng === 0);
  return (
    <MapContainer
      center={hasPoint ? [lat!, lng!] : DEFAULT_CENTER}
      zoom={hasPoint ? 15 : DEFAULT_ZOOM}
    >
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      <CleanAttribution />
      <ClickHandler onPick={onPick} />
      <FlyTo focus={focus} />
      {hasPoint && (
        <CircleMarker
          center={[lat!, lng!]}
          radius={10}
          pathOptions={{ color: '#fff', weight: 2, fillColor: '#6B9080', fillOpacity: 1 }}
        />
      )}
    </MapContainer>
  );
}
