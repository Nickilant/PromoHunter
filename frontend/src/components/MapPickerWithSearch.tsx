import { useEffect, useState } from 'react';

import { geocodeAddress, geocodeCity } from '../utils/geocode';
import { LocationPickerMap, MapFocus } from './MapView';
import Icon from './Icon';

interface Props {
  lat: number | null;
  lng: number | null;
  city: string | null;
  onPick: (lat: number, lng: number) => void;
}

// Пикер координат с поиском по адресу: нашли — карта подлетела,
// тап по карте ставит точку
export default function MapPickerWithSearch({ lat, lng, city, onPick }: Props) {
  const [query, setQuery] = useState('');
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Точка ещё не выбрана — начинаем с города формы, а не с дефолта карты
  useEffect(() => {
    if (lat !== null || lng !== null || !city) return;
    let cancelled = false;
    geocodeCity(city).then((point) => {
      if (point && !cancelled) {
        setFocus({ lat: point.lat, lng: point.lng, zoom: 11 });
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city]);

  const search = async () => {
    const q = query.trim();
    if (!q || searching) return;
    setSearching(true);
    setError(null);
    const point = await geocodeAddress(q, city);
    setSearching(false);
    if (point) {
      setFocus({ lat: point.lat, lng: point.lng, zoom: 16 });
    } else {
      setError('Адрес не нашёлся — попробуйте уточнить');
    }
  };

  return (
    <div className="map-picker-search">
      <div className="map-picker-search-bar">
        <input
          className="search-input"
          type="search"
          placeholder={`Найти адрес${city ? ` в городе ${city}` : ''}…`}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              search();
            }
          }}
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={searching}
          onClick={search}
          aria-label="Найти адрес"
        >
          {searching ? <span className="spinner" /> : <Icon name="search" size={18} />}
        </button>
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="hint">Найдите адрес, затем тапните по карте — точка встанет туда</div>
      <div className="map-picker">
        <LocationPickerMap lat={lat} lng={lng} onPick={onPick} focus={focus} />
      </div>
    </div>
  );
}
