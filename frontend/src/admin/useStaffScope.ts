import { useEffect, useState } from 'react';

import { api } from '../api/client';
import type { StaffScope } from '../types';

/**
 * Кто открыл админку: глобальный админ или городской модератор.
 * По этому интерфейс прячет недоступные разделы — но решает всё равно
 * сервер, здесь только удобство.
 */
export function useStaffScope(): StaffScope | null {
  const [scope, setScope] = useState<StaffScope | null>(null);

  useEffect(() => {
    api.get<StaffScope>('/admin/scope').then(setScope).catch(() => {});
  }, []);

  return scope;
}
