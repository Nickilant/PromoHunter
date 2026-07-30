import { useEffect, useState } from 'react';

import { api, ApiError } from '../api/client';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import type { GameStandings } from '../types';
import { FACTION_TITLE } from '../utils/faction';
import { POINTS, pluralize } from '../utils/plural';
import FactionPicker from './FactionPicker';
import Icon from './Icon';
import { useToast } from './Toast';

/** Настройки игрового режима в профиле: тумблер, сторона, сезонный расклад. */
export default function GameSettings() {
  const { available, enabled, faction, config, setMode } = useGame();
  const { city } = useCity();
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);
  const [standings, setStandings] = useState<GameStandings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (!enabled || !city) {
      setStandings(null);
      return;
    }
    api
      .get<GameStandings>(`/game/standings?city=${encodeURIComponent(city)}`)
      .then(setStandings)
      .catch(() => {});
  }, [enabled, city]);

  if (!available) return null;

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await setMode(!enabled);
      toast(enabled ? 'Игровой режим выключен' : 'Игровой режим включён');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не получилось переключить режим');
    } finally {
      setBusy(false);
    }
  };

  const switchAt = config?.me?.can_switch_at
    ? new Date(config.me.can_switch_at)
    : null;
  const canSwitch = switchAt === null || switchAt.getTime() <= Date.now();

  return (
    <>
      <div className="section-title">Игровой режим</div>
      <div className="game-settings">
        <button
          className={`game-toggle${enabled ? ' on' : ''}`}
          onClick={toggle}
          disabled={busy}
          role="switch"
          aria-checked={enabled}
        >
          <span className="game-toggle-body">
            <span className="game-toggle-title">
              <Icon name="gamepad" size={18} />
              Захват точек фракциями
            </span>
            <span className="game-toggle-meta">
              {enabled
                ? 'Владение точек, шкалы и таймеры показываются'
                : 'Выключено — сервис работает как обычный поиск акций'}
            </span>
          </span>
          <span className="game-switch" aria-hidden="true">
            <span className="game-switch-knob" />
          </span>
        </button>

        {enabled && (
          <div className="game-side-row">
            <span className="muted">Ваша сторона</span>
            {faction ? (
              <span className={`faction-chip ${faction}`}>
                <Icon name="shield" size={14} strokeWidth={2} />
                {FACTION_TITLE[faction]}
              </span>
            ) : (
              <button
                className="btn btn-primary btn-small"
                onClick={() => setPicking(true)}
              >
                <Icon name="flag" size={15} />
                Выбрать
              </button>
            )}
          </div>
        )}

        {enabled && faction && (
          <div className="game-settings-note">
            {canSwitch ? (
              <button className="btn btn-ghost btn-small" onClick={() => setPicking(true)}>
                Сменить сторону
              </button>
            ) : (
              <span className="muted">
                Сменить сторону можно после{' '}
                {switchAt!.toLocaleDateString('ru-RU')}
              </span>
            )}
          </div>
        )}

        {error && <div className="form-error">{error}</div>}
      </div>

      {enabled && standings && standings.points_total > 0 && (
        <div className="standings-card">
          <div className="standings-head">
            <span>
              Сезон {formatSeason(standings.season)} · {standings.city}
            </span>
            <span className="muted">
              {standings.points_total} {pluralize(standings.points_total, POINTS)}
            </span>
          </div>
          {standings.standings.map((row) => {
            // Полоса — текущая доля владения: её видно сразу. Средняя доля за
            // сезон копится джобой и в начале месяца близка к нулю.
            const now = standings.points_total
              ? row.points_held / standings.points_total
              : 0;
            return (
              <div className={`standings-row ${row.faction}`} key={row.faction}>
                <span className="standings-title">{row.title}</span>
                <span className="standings-bar">
                  <span
                    className={`standings-fill ${row.faction}`}
                    style={{ width: `${Math.round(now * 100)}%` }}
                  />
                </span>
                <span className="standings-value">
                  {row.points_held} {pluralize(row.points_held, POINTS)}
                </span>
              </div>
            );
          })}
          <div className="standings-foot muted">
            Свободных {pluralize(standings.neutral, POINTS)}: {standings.neutral}.
            Место в сезоне — по средней доле удержанных точек за месяц: у зелёных{' '}
            {formatShare(standings.standings[0]?.held_share)}, у фиолетовых{' '}
            {formatShare(standings.standings[1]?.held_share)}.
          </div>
        </div>
      )}

      {picking && <FactionPicker onDone={() => setPicking(false)} />}
    </>
  );
}

const MONTHS = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];

function formatSeason(season: string): string {
  const [year, month] = season.split('-');
  const index = Number(month) - 1;
  return MONTHS[index] ? `${MONTHS[index]} ${year}` : season;
}

function formatShare(share: number | undefined): string {
  if (!share) return '0%';
  const percent = share * 100;
  return percent < 1 ? '<1%' : `${Math.round(percent)}%`;
}
