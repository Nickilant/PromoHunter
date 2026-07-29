import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import type { TelegramInfo } from '../types';

interface CodeRequestResponse {
  delivery: 'sent' | 'await_contact';
  bot_username: string | null;
}

export default function RegisterPage() {
  const [phone, setPhone] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  // подтверждение номера кодом из Telegram
  const [tgEnabled, setTgEnabled] = useState(false);
  const [codeRequest, setCodeRequest] = useState<CodeRequestResponse | null>(null);
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);

  const { register } = useAuth();
  const { city } = useCity();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get<TelegramInfo>('/telegram/info')
      .then((info) => setTgEnabled(info.enabled))
      .catch(() => {});
  }, []);

  const onPhoneChange = (value: string) => {
    setPhone(value);
    // смена номера сбрасывает подтверждение
    setCodeRequest(null);
    setCode('');
    setVerified(false);
    setError(null);
  };

  const requestCode = async () => {
    setError(null);
    setVerifying(true);
    try {
      const resp = await api.post<CodeRequestResponse>(
        '/auth/phone-verification/request',
        { phone },
      );
      setCodeRequest(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не получилось отправить код');
    } finally {
      setVerifying(false);
    }
  };

  const confirmCode = async () => {
    setError(null);
    setVerifying(true);
    try {
      await api.post('/auth/phone-verification/confirm', { phone, code });
      setVerified(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неверный код');
    } finally {
      setVerifying(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      // город из сессии станет городом по умолчанию в профиле
      await register(phone, password, displayName, city);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не получилось зарегистрироваться');
    } finally {
      setSending(false);
    }
  };

  const canSubmit = !sending && (!tgEnabled || verified);

  return (
    <div className="auth-page">
      <div className="logo">🏷️</div>
      <h1>Регистрация</h1>
      <form onSubmit={submit}>
        <div className="field">
          <label>Номер телефона</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => onPhoneChange(e.target.value)}
            autoComplete="tel"
            placeholder="+7 999 123-45-67"
            required
            disabled={verified}
          />
          {tgEnabled && verified && (
            <div className="form-success">✓ Номер подтверждён</div>
          )}
        </div>

        {tgEnabled && !verified && (
          <>
            {codeRequest === null ? (
              <button
                type="button"
                className="btn btn-ghost btn-block"
                onClick={requestCode}
                disabled={!phone.trim() || verifying}
              >
                {verifying ? 'Отправляем…' : 'Подтвердить номер'}
              </button>
            ) : (
              <>
                <div className="verify-block">
                  {codeRequest.delivery === 'sent' ? (
                    <>Код отправлен вам в Telegram — введите его ниже.</>
                  ) : (
                    <>
                      Откройте бота, нажмите <b>Start</b>, затем
                      «📱 Подтвердить номер» — бот пришлёт код. Введите его ниже.
                      {codeRequest.bot_username && (
                        <a
                          className="btn btn-primary btn-block"
                          style={{ marginTop: 8 }}
                          href={`https://t.me/${codeRequest.bot_username}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Открыть бота
                        </a>
                      )}
                    </>
                  )}
                </div>
                <div className="field">
                  <label>Код из Telegram</label>
                  <div className="code-row">
                    <input
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={8}
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="0000"
                    />
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={confirmCode}
                      disabled={!code.trim() || verifying}
                    >
                      {verifying ? '…' : 'Подтвердить'}
                    </button>
                  </div>
                  <div className="hint">
                    Не пришёл код?{' '}
                    <button type="button" className="link-btn" onClick={requestCode}>
                      Отправить ещё раз
                    </button>
                  </div>
                </div>
              </>
            )}
          </>
        )}

        <div className="field">
          <label>Имя</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
            required
          />
        </div>
        <div className="field">
          <label>Пароль</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={6}
            required
          />
          <div className="hint">Минимум 6 символов</div>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={!canSubmit}>
          {sending ? 'Создаём…' : 'Создать аккаунт'}
        </button>
        {tgEnabled && !verified && (
          <div className="hint" style={{ textAlign: 'center' }}>
            Кнопка станет активной после подтверждения номера
          </div>
        )}
      </form>
      <div className="auth-switch">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </div>
    </div>
  );
}
