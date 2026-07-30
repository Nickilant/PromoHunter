import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { useDismiss } from '../hooks/useDismiss';
import { useGame } from '../hooks/useGame';
import { ApiError } from '../api/client';
import type { Faction, FactionInfo } from '../types';
import { PLAYERS, pluralize } from '../utils/plural';
import Icon from './Icon';

/**
 * Выбор стороны. Баланс держим двумя рычагами:
 * перекошенная фракция закрывается для набора, а слабейшая получает
 * прибавку к силе чека — играть за меньшинство выгоднее.
 */
export default function FactionPicker({ onDone }: { onDone: () => void }) {
  const { config, chooseFaction } = useGame();
  const { user } = useAuth();
  const [busy, setBusy] = useState<Faction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { closing, dismiss, onAnimationEnd } = useDismiss(onDone);

  const factions = config?.factions ?? [];

  const pick = async (faction: FactionInfo) => {
    if (busy || faction.join_blocked) return;
    setBusy(faction.key);
    setError(null);
    try {
      await chooseFaction(faction.key);
      dismiss();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не получилось выбрать сторону');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className={`faction-picker${closing ? ' closing' : ''}`}
      onAnimationEnd={onAnimationEnd}
    >
      <div className="faction-picker-inner">
        <div className="faction-picker-head">
          <h1>Выберите сторону</h1>
          <div className="subtitle">
            {config?.city
              ? `Расклад сил в городе ${config.city}`
              : 'Сторона одна на все города'}
          </div>
        </div>

        {!user && (
          <div className="faction-guest">
            <Icon name="user" size={17} />
            <span>
              Смотреть карту можно и так, но чтобы встать за сторону, нужен вход
            </span>
            <Link className="btn btn-primary btn-small" to="/login" onClick={dismiss}>
              Войти
            </Link>
          </div>
        )}

        <div className="faction-cards">
          {factions.map((faction) => {
            const percent = Math.round(faction.share * 100);
            const bonus = Math.round(faction.underdog_bonus * 100);
            const disabled = !user || faction.join_blocked || busy !== null;
            return (
              <button
                key={faction.key}
                className={`faction-card ${faction.key}${
                  faction.join_blocked ? ' blocked' : ''
                }`}
                onClick={() => pick(faction)}
                disabled={disabled}
                aria-busy={busy === faction.key}
              >
                <span className="faction-card-mark">
                  {busy === faction.key ? (
                    <span className="spinner" />
                  ) : (
                    <Icon name="shield" size={26} strokeWidth={1.8} />
                  )}
                </span>
                <span className="faction-card-body">
                  <span className="faction-card-title">{faction.title}</span>
                  <span className="faction-card-meta">
                    {faction.members === 0
                      ? 'пока никого'
                      : `${faction.members} ${pluralize(faction.members, PLAYERS)} · ${percent}%`}
                  </span>
                  {faction.join_blocked ? (
                    <span className="faction-card-note blocked">
                      Набор закрыт — перевес
                    </span>
                  ) : bonus > 0 ? (
                    <span className="faction-card-note bonus">
                      +{bonus}% к силе чека за меньшинство
                    </span>
                  ) : (
                    <span className="faction-card-note">Силы равны</span>
                  )}
                </span>
                <span className="faction-card-share">
                  <span
                    className={`faction-card-share-fill ${faction.key}`}
                    style={{ width: `${percent}%` }}
                  />
                </span>
              </button>
            );
          })}
        </div>

        {error && <div className="form-error">{error}</div>}

        <div className="faction-picker-note">
          Сторону можно сменить раз в месяц — и только на ту, где людей меньше.
        </div>
        <button className="btn btn-ghost btn-block" onClick={dismiss}>
          Позже
        </button>
      </div>
    </div>
  );
}
