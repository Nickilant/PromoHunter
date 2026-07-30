import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { api } from '../api/client';
import type { Faction, GameConfig, PointControl, User } from '../types';
import { useAuth } from './useAuth';
import { useCity } from './useCity';

// Ответ «включать или нет» помним локально: спросить надо сразу после
// выбора города, ещё до входа, а профиль подхватит выбор при авторизации.
const MODE_KEY = 'promohunter_game_mode';
const ASKED_KEY = 'promohunter_game_asked';
const LAYER_KEY = 'promohunter_game_layer';

const POINTS_REFRESH_MS = 45000;

interface GameContextValue {
  /** Фича доступна на сервисе */
  available: boolean;
  /** Игровой режим включён у этого пользователя (или в этой сессии) */
  enabled: boolean;
  /** Спрашивали ли уже про режим */
  asked: boolean;
  faction: Faction | null;
  config: GameConfig | null;
  /** Слой владения на карте виден */
  layerVisible: boolean;
  toggleLayer: () => void;
  points: Map<number, PointControl>;
  pointOf: (restaurantId: number) => PointControl | undefined;
  /** Растёт при каждой загрузке табло — по нему обновляются детали точки */
  pointsVersion: number;
  setMode: (enabled: boolean) => Promise<void>;
  chooseFaction: (faction: Faction) => Promise<void>;
  refreshPoints: () => void;
  refreshConfig: () => void;
}

const GameContext = createContext<GameContextValue | null>(null);

function readFlag(key: string): boolean {
  return localStorage.getItem(key) === '1';
}

export function GameProvider({ children }: { children: ReactNode }) {
  const { user, loading, refresh } = useAuth();
  const { city } = useCity();

  const [config, setConfig] = useState<GameConfig | null>(null);
  const [localMode, setLocalMode] = useState(() => readFlag(MODE_KEY));
  const [localAsked, setLocalAsked] = useState(() => readFlag(ASKED_KEY));
  const [layerVisible, setLayerVisible] = useState(
    () => localStorage.getItem(LAYER_KEY) !== '0',
  );
  const [points, setPoints] = useState<Map<number, PointControl>>(new Map());
  const [configTick, setConfigTick] = useState(0);
  const [pointsTick, setPointsTick] = useState(0);
  const [pointsVersion, setPointsVersion] = useState(0);

  // Профиль — источник истины, локальный флаг нужен только до входа
  const enabled = user ? user.game_mode : localMode;
  const asked = user ? user.game_asked : localAsked;
  const faction = user?.faction ?? null;
  const available = config?.enabled ?? false;

  useEffect(() => {
    if (loading) return;
    const params = city ? `?city=${encodeURIComponent(city)}` : '';
    api
      .get<GameConfig>(`/game/config${params}`)
      .then(setConfig)
      .catch(() => setConfig(null));
  }, [city, user, loading, configTick]);

  // Локальный ответ переносим в профиль: человек ответил до входа
  const synced = useRef(false);
  useEffect(() => {
    if (!user || synced.current) return;
    if (!localAsked || user.game_asked) return;
    synced.current = true;
    api
      .post<User>('/game/mode', { enabled: localMode })
      .then(() => refresh())
      .catch(() => {});
  }, [user, localAsked, localMode, refresh]);

  const loadPoints = useCallback(() => {
    if (!city || !available || !enabled) {
      setPoints(new Map());
      return;
    }
    api
      .get<PointControl[]>(`/game/points?city=${encodeURIComponent(city)}`)
      .then((list) => {
        setPoints(new Map(list.map((p) => [p.restaurant_id, p])));
        setPointsVersion((v) => v + 1);
      })
      .catch(() => {});
  }, [city, available, enabled]);

  useEffect(() => {
    loadPoints();
    if (!city || !available || !enabled) return;
    const timer = window.setInterval(loadPoints, POINTS_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadPoints, city, available, enabled, pointsTick]);

  const setMode = useCallback(
    async (value: boolean) => {
      localStorage.setItem(MODE_KEY, value ? '1' : '0');
      localStorage.setItem(ASKED_KEY, '1');
      setLocalMode(value);
      setLocalAsked(true);
      if (user) {
        await api.post<User>('/game/mode', { enabled: value });
        await refresh();
      }
      setConfigTick((t) => t + 1);
    },
    [user, refresh],
  );

  const chooseFaction = useCallback(
    async (value: Faction) => {
      await api.post<User>('/game/faction', { faction: value });
      await refresh();
      setConfigTick((t) => t + 1);
      setPointsTick((t) => t + 1);
    },
    [refresh],
  );

  const toggleLayer = useCallback(() => {
    setLayerVisible((visible) => {
      localStorage.setItem(LAYER_KEY, visible ? '0' : '1');
      return !visible;
    });
  }, []);

  const pointOf = useCallback(
    (restaurantId: number) => points.get(restaurantId),
    [points],
  );

  const value = useMemo(
    () => ({
      available,
      enabled: available && enabled,
      asked,
      faction,
      config,
      layerVisible,
      toggleLayer,
      points,
      pointOf,
      pointsVersion,
      setMode,
      chooseFaction,
      refreshPoints: () => setPointsTick((t) => t + 1),
      refreshConfig: () => setConfigTick((t) => t + 1),
    }),
    [
      available,
      enabled,
      asked,
      faction,
      config,
      layerVisible,
      toggleLayer,
      points,
      pointOf,
      pointsVersion,
      setMode,
      chooseFaction,
    ],
  );

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
}

export function useGame(): GameContextValue {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within GameProvider');
  return ctx;
}
