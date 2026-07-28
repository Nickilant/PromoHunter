// Весь код Leaflet изолирован в этом компоненте,
// чтобы карту можно было заменить (например, на Яндекс.Карты), не трогая остальное.
import 'leaflet/dist/leaflet.css';

import { useEffect } from 'react';
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet';

import type { RestaurantListItem } from '../types';

const DEFAULT_CENTER: [number, number] = [59.935, 30.325]; // Санкт-Петербург
const DEFAULT_ZOOM = 12;
const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors';

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
    >
      📍
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

interface RestaurantsMapProps {
  restaurants: RestaurantListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  focus: MapFocus | null;
  searchPoint: MapFocus | null;
}

export function RestaurantsMap({
  restaurants,
  selectedId,
  onSelect,
  focus,
  searchPoint,
}: RestaurantsMapProps) {
  return (
    <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} zoomControl={false}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      <FitToMarkers points={restaurants.map((r) => [r.lat, r.lng])} />
      <FlyTo focus={focus} />
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
}

export function LocationPickerMap({ lat, lng, onPick }: LocationPickerProps) {
  const hasPoint = lat !== null && lng !== null && !(lat === 0 && lng === 0);
  return (
    <MapContainer
      center={hasPoint ? [lat!, lng!] : DEFAULT_CENTER}
      zoom={hasPoint ? 15 : DEFAULT_ZOOM}
    >
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
      <ClickHandler onPick={onPick} />
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
