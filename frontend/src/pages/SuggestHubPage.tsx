import { Link } from 'react-router-dom';

// Хаб «＋»: что хочет добавить пользователь
export default function SuggestHubPage() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Добавить в сервис</h1>
      </div>
      <div className="suggest-hub">
        <Link to="/suggest/promotion" className="suggest-hub-card">
          <span className="suggest-hub-icon" style={{ background: 'var(--accent)' }}>
            🏷️
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Заявить акцию</span>
            <span className="brand-card-meta">
              Видели акцию, которой нет в сервисе? Расскажите — модератор добавит
            </span>
          </span>
          <span className="chevron-right">›</span>
        </Link>
        <Link to="/suggest/restaurant" className="suggest-hub-card">
          <span className="suggest-hub-icon" style={{ background: 'var(--primary)' }}>
            📍
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Добавить ресторан</span>
            <span className="brand-card-meta">
              Точки нет на карте? Укажите адрес и место — добавим после проверки
            </span>
          </span>
          <span className="chevron-right">›</span>
        </Link>
      </div>
      <div className="hint" style={{ textAlign: 'center' }}>
        За одобренные заявки начисляются очки рейтинга
      </div>
    </div>
  );
}
