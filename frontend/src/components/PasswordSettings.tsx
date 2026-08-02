import { FormEvent, useState } from 'react';

import { api, ApiError } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { AuthResponse } from '../types';
import Icon from './Icon';
import { useToast } from './Toast';

/** Смена пароля в профиле.
 *
 * У аккаунта, заведённого входом через Telegram, пароля никогда не было —
 * текущий у него не спрашиваем, а кнопку называем «Задать пароль».
 */
export default function PasswordSettings() {
  const { user, applyAuth } = useAuth();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const toast = useToast();

  if (!user) return null;
  const hasPassword = user.has_password;

  const close = () => {
    setOpen(false);
    setCurrent('');
    setNext('');
    setRepeat('');
    setError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next !== repeat) {
      setError('Пароли не совпадают');
      return;
    }
    setSending(true);
    setError(null);
    try {
      const resp = await api.post<AuthResponse>('/auth/password', {
        current_password: hasPassword ? current : null,
        new_password: next,
      });
      // Смена обесценивает все прежние токены, включая наш — берём свежий
      applyAuth(resp);
      close();
      toast(hasPassword ? 'Пароль изменён' : 'Пароль задан');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не получилось сменить пароль');
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <div className="section-title">Пароль</div>
      <div className="profile-card">
        {!open && (
          <>
            {!hasPassword && (
              <div className="row">
                <span className="muted">Вход</span>
                <span>только через Telegram</span>
              </div>
            )}
            <button className="btn btn-ghost" onClick={() => setOpen(true)}>
              <Icon name="lock" size={17} />
              {hasPassword ? 'Сменить пароль' : 'Задать пароль'}
            </button>
          </>
        )}

        {open && (
          <form onSubmit={submit} className="password-form">
            {hasPassword && (
              <div className="field">
                <label htmlFor="pwd-current">Текущий пароль</label>
                <input
                  id="pwd-current"
                  type="password"
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="field">
              <label htmlFor="pwd-new">Новый пароль</label>
              <input
                id="pwd-new"
                type="password"
                autoComplete="new-password"
                minLength={6}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="pwd-repeat">Повторите новый</label>
              <input
                id="pwd-repeat"
                type="password"
                autoComplete="new-password"
                minLength={6}
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                required
              />
            </div>

            {error && <div className="form-error">{error}</div>}
            <div className="muted" style={{ fontSize: 13 }}>
              Не короче 6 символов. После смены остальные устройства попросят
              войти заново.
            </div>

            <div className="password-form-actions">
              <button type="button" className="btn btn-ghost" onClick={close}>
                Отмена
              </button>
              <button className="btn btn-primary" disabled={sending}>
                {sending ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </div>
          </form>
        )}
      </div>
    </>
  );
}
