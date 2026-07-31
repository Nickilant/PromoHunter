import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { LogoMark } from '../components/Icon';
import { DEVELOPER_TELEGRAM, DEVELOPER_TELEGRAM_URL } from '../utils/contacts';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await login(phone, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не получилось войти');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="logo"><LogoMark size={68} /></div>
      <h1>Вход</h1>
      <form onSubmit={submit}>
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
        </div>
        <div className="field">
          <label>Пароль</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={sending}>
          {sending ? 'Входим…' : 'Войти'}
        </button>
      </form>
      <div className="auth-switch">
        Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
      </div>
      {/* Восстановления пароля нет: если номер привязан к Telegram, вход
          оттуда работает без пароля, а новый задаётся в профиле */}
      <div className="auth-help">
        Забыли пароль? Откройте сервис из Telegram — там вход без пароля,
        а новый можно задать в профиле. Не получается —{' '}
        <a href={DEVELOPER_TELEGRAM_URL} target="_blank" rel="noreferrer">
          напишите @{DEVELOPER_TELEGRAM}
        </a>
      </div>
    </div>
  );
}
