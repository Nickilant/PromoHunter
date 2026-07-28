import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await register(email, password, displayName);
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
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
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
