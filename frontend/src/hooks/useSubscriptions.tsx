import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { Subscription } from '../types';
import { useAuth } from './useAuth';

interface SubscriptionsContextValue {
  subscriptions: Subscription[];
  isSubscribedToRestaurant: (id: number) => boolean;
  isSubscribedToPromotion: (id: number) => boolean;
  toggleRestaurant: (id: number) => Promise<void>;
  togglePromotion: (id: number) => Promise<void>;
  remove: (id: number) => Promise<void>;
}

const SubscriptionsContext = createContext<SubscriptionsContextValue | null>(null);

export function SubscriptionsProvider({ children }: { children: ReactNode }) {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const { user } = useAuth();
  const toast = useToast();

  const load = useCallback(() => {
    if (!user) {
      setSubscriptions([]);
      return;
    }
    api.get<Subscription[]>('/subscriptions/mine').then(setSubscriptions).catch(() => {});
  }, [user]);

  useEffect(load, [load]);

  const findByRestaurant = (id: number) =>
    subscriptions.find((s) => s.restaurant?.id === id);
  const findByPromotion = (id: number) =>
    subscriptions.find((s) => s.promotion?.id === id);

  const toggle = async (body: object, existing: Subscription | undefined) => {
    try {
      if (existing) {
        await api.delete(`/subscriptions/${existing.id}`);
        toast('Подписка отключена');
      } else {
        await api.post('/subscriptions', body);
        toast('Подписка оформлена — бот пришлёт новости');
      }
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не получилось');
    }
  };

  const remove = async (id: number) => {
    try {
      await api.delete(`/subscriptions/${id}`);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Не получилось');
    }
  };

  return (
    <SubscriptionsContext.Provider
      value={{
        subscriptions,
        isSubscribedToRestaurant: (id) => Boolean(findByRestaurant(id)),
        isSubscribedToPromotion: (id) => Boolean(findByPromotion(id)),
        toggleRestaurant: (id) => toggle({ restaurant_id: id }, findByRestaurant(id)),
        togglePromotion: (id) => toggle({ promotion_id: id }, findByPromotion(id)),
        remove,
      }}
    >
      {children}
    </SubscriptionsContext.Provider>
  );
}

export function useSubscriptions(): SubscriptionsContextValue {
  const ctx = useContext(SubscriptionsContext);
  if (!ctx) throw new Error('useSubscriptions must be used within SubscriptionsProvider');
  return ctx;
}
