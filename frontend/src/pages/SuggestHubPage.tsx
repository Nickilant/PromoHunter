import { Link } from 'react-router-dom';
import Icon from '../components/Icon';

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
            <Icon name="tag" size={26} strokeWidth={1.8} />
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Заявить акцию</span>
            <span className="brand-card-meta">
              Видели акцию, которой нет в сервисе? Расскажите — модератор добавит
            </span>
          </span>
          <span className="chevron-right"><Icon name="chevronRight" size={20} /></span>
        </Link>
        <Link to="/suggest/restaurant" className="suggest-hub-card">
          <span className="suggest-hub-icon" style={{ background: 'var(--primary)' }}>
            <Icon name="pin" size={26} strokeWidth={1.8} />
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Добавить ресторан</span>
            <span className="brand-card-meta">
              Точки нет на карте? Укажите адрес и место — добавим после проверки
            </span>
          </span>
          <span className="chevron-right"><Icon name="chevronRight" size={20} /></span>
        </Link>
      </div>
      <div className="hint" style={{ textAlign: 'center' }}>
        За одобренные заявки начисляются очки рейтинга
      </div>
    </div>
  );
}
