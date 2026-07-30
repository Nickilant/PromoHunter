import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import FactionPicker from './FactionPicker';
import GameOnboarding from './GameOnboarding';

// Экраны, которые нельзя закрывать игровым оверлеем: на них человек
// решает другую задачу — входит в аккаунт или работает в админке
const KEEP_CLEAR = ['/login', '/register', '/admin'];

/**
 * Порядок первого запуска: город → «включить игровой режим?» → сторона.
 * Про режим спрашиваем один раз, выбор стороны можно отложить — тогда
 * предложим снова в следующий заход или из профиля.
 */
export default function GameGate() {
  const { city } = useCity();
  const { user, loading } = useAuth();
  const { available, enabled, asked, faction } = useGame();
  const { pathname } = useLocation();
  const [factionPostponed, setFactionPostponed] = useState(false);

  // Новый вход — снова показываем выбор стороны, если её так и нет
  useEffect(() => {
    setFactionPostponed(false);
  }, [user?.id]);

  if (KEEP_CLEAR.some((path) => pathname.startsWith(path))) return null;
  if (loading || !city || !available) return null;
  if (!asked) return <GameOnboarding onDone={() => {}} />;
  // Гостю сторону тоже показываем: расклад сил виден сразу, а встать
  // за фракцию он предложит через вход — иначе экран просто не появится
  if (enabled && faction === null && !factionPostponed) {
    return <FactionPicker onDone={() => setFactionPostponed(true)} />;
  }
  return null;
}
