// Весь код Leaflet изолирован в этом компоненте,
// чтобы карту можно было заменить (например, на Яндекс.Карты), не трогая остальное.
import 'leaflet/dist/leaflet.css';

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

interface RestaurantsMapProps {
  restaurants: RestaurantListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function RestaurantsMap({ restaurants, selectedId, onSelect }: RestaurantsMapProps) {
  return (
    <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} zoomControl={false}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
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
