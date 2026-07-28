import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

import CityPicker from '../components/CityPicker';
import { useAuth } from './useAuth';

const CITY_KEY = 'promohunter_city';

interface CityContextValue {
  /** Рабочий город: выбор в сессии > город из профиля > null (спросим) */
  city: string | null;
  setCity: (city: string) => void;
  openPicker: () => void;
}

const CityContext = createContext<CityContextValue | null>(null);

export function CityProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const [sessionCity, setSessionCity] = useState<string | null>(
    () => localStorage.getItem(CITY_KEY),
  );
  const [pickerOpen, setPickerOpen] = useState(false);

  const city = useMemo(
    () => sessionCity ?? user?.city ?? null,
    [sessionCity, user],
  );

  const setCity = useCallback((value: string) => {
    localStorage.setItem(CITY_KEY, value);
    setSessionCity(value);
    setPickerOpen(false);
  }, []);

  const openPicker = useCallback(() => setPickerOpen(true), []);

  // Пока не знаем, авторизован ли пользователь, — не спрашиваем город зря
  const needPicker = !loading && (pickerOpen || city === null);

  return (
    <CityContext.Provider value={{ city, setCity, openPicker }}>
      {children}
      {needPicker && (
        <CityPicker
          current={city}
          onSelect={setCity}
          onClose={city !== null ? () => setPickerOpen(false) : undefined}
        />
      )}
    </CityContext.Provider>
  );
}

export function useCity(): CityContextValue {
  const ctx = useContext(CityContext);
  if (!ctx) throw new Error('useCity must be used within CityProvider');
  return ctx;
}
