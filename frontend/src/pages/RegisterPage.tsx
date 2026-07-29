import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';

export default function RegisterPage() {
  const [phone, setPhone] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { register } = useAuth();
  const { city } = useCity();
  const navigate = useNavigate();

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

  return (
    <div className="auth-page">
      <div className="logo">🏷️</div>
      <h1>Регистрация</h1>
      <form onSubmit={submit}>
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
          <label>Номер телефона</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
            placeholder="+7 999 123-45-67"
            required
          />
          <div className="hint">
            После регистрации номер можно подтвердить через Telegram-бота
            (кнопка в профиле) — подтверждённым отчётам больше доверия
          </div>
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
        <button className="btn btn-primary btn-block" disabled={sending}>
          {sending ? 'Создаём…' : 'Создать аккаунт'}
        </button>
      </form>
      <div className="auth-switch">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </div>
    </div>
  );
}
