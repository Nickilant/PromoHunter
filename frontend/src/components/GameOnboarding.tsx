import { useState } from 'react';

import { useDismiss } from '../hooks/useDismiss';
import { useGame } from '../hooks/useGame';
import Icon from './Icon';

/**
 * Спрашиваем про игровой режим один раз — сразу после выбора города.
 * Отказ ничего не включает: сервис остаётся точно таким, как был.
 */
export default function GameOnboarding({ onDone }: { onDone: () => void }) {
  const { setMode, config } = useGame();
  const [busy, setBusy] = useState<'yes' | 'no' | null>(null);
  const { closing, dismiss, onAnimationEnd } = useDismiss(onDone);

  const answer = async (enabled: boolean) => {
    if (busy) return;
    setBusy(enabled ? 'yes' : 'no');
    try {
      await setMode(enabled);
    } finally {
      setBusy(null);
      dismiss();
    }
  };

  const minSum = config?.min_sum_rubles ?? 50;

  return (
    <div
      className={`game-onboarding${closing ? ' closing' : ''}`}
      onAnimationEnd={onAnimationEnd}
    >
      <div className="game-onboarding-inner">
        <div className="game-hero" aria-hidden="true">
          <span className="game-hero-half green">
            <Icon name="shield" size={30} strokeWidth={1.8} />
          </span>
          <span className="game-hero-clash">
            <Icon name="swords" size={22} strokeWidth={2} />
          </span>
          <span className="game-hero-half purple">
            <Icon name="shield" size={30} strokeWidth={1.8} />
          </span>
        </div>

        <h1>Играть за территорию?</h1>
        <p className="game-onboarding-lead">
          Кроме поиска акций у нас есть игра: две фракции делят точки на карте.
          Точку забирает та сторона, которая приносит больше чеков.
        </p>

        <ul className="game-facts">
          <li>
            <Icon name="receipt" size={17} />
            <span>
              Захват идёт только по чеку с кассы — от {minSum} ₽ и рядом с точкой.
              Написать «есть», не покупая, не получится
            </span>
          </li>
          <li>
            <Icon name="timer" size={17} />
            <span>
              У каждой стороны своя шкала. Идёт шкала того, у кого чеков больше;
              чья заполнилась первой — та и решила исход
            </span>
          </li>
          <li>
            <Icon name="layers" size={17} />
            <span>Владение точек — отдельный слой на карте, его можно скрыть</span>
          </li>
        </ul>

        <div className="game-onboarding-actions">
          <button
            className={`btn btn-primary btn-block${busy === 'yes' ? ' is-busy' : ''}`}
            onClick={() => answer(true)}
            disabled={busy !== null}
            aria-busy={busy === 'yes'}
          >
            {busy === 'yes' ? <span className="spinner" /> : <Icon name="gamepad" size={18} />}
            Включить игровой режим
          </button>
          <button
            className="btn btn-ghost btn-block"
            onClick={() => answer(false)}
            disabled={busy !== null}
          >
            Нет, только акции
          </button>
        </div>
        <div className="game-onboarding-note">
          Передумать можно в любой момент — переключатель в профиле
        </div>
      </div>
    </div>
  );
}
