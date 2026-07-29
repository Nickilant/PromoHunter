import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type {
  AdminBrand,
  AdminRestaurantSuggestion,
  RestaurantSuggestionGroup,
} from '../types';
import { formatDateTime } from '../utils/time';
import type { AdminOutletContext } from './AdminLayout';
import CollapsibleGroup from './CollapsibleGroup';
import RestaurantForm, { RestaurantFormValue } from './RestaurantForm';
import Icon from '../components/Icon';

const STATUS_LABELS: Record<string, { text: string; cls: string }> = {
  pending: { text: 'Ожидает', cls: 'warn' },
  approved: { text: 'Одобрена', cls: 'ok' },
  rejected: { text: 'Отклонена', cls: 'error' },
};

export default function AdminRestaurantSuggestions() {
  const [groups, setGroups] = useState<RestaurantSuggestionGroup[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [approving, setApproving] = useState<{
    suggestion: AdminRestaurantSuggestion;
    initial: RestaurantFormValue;
  } | null>(null);
  const [rejecting, setRejecting] = useState<AdminRestaurantSuggestion | null>(null);
  const [rejectComment, setRejectComment] = useState('');
  const [rejectSpam, setRejectSpam] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { refreshPendingCount } = useOutletContext<AdminOutletContext>();
  const toast = useToast();

  const load = () => {
    const params = statusFilter ? `?status=${statusFilter}` : '';
    api
      .get<RestaurantSuggestionGroup[]>(`/admin/restaurant-suggestions${params}`)
      .then(setGroups)
      .catch(() => {});
  };

  useEffect(() => {
    api.get<AdminBrand[]>('/admin/brands').then(setBrands).catch(() => {});
  }, []);

  useEffect(load, [statusFilter]);

  const openApprove = (s: AdminRestaurantSuggestion) => {
    setError(null);
    setApproving({
      suggestion: s,
      initial: {
        brand_id: String(s.brand.id),
        title: s.title ?? '',
        city: s.city,
        address: s.address,
        lat: String(s.lat),
        lng: String(s.lng),
        is_active: true,
      },
    });
  };

  const approve = async (value: RestaurantFormValue) => {
    if (!approving) return;
    setError(null);
    try {
      await api.post(
        `/admin/restaurant-suggestions/${approving.suggestion.id}/approve`,
        {
          brand_id: Number(value.brand_id),
          title: value.title || null,
          city: value.city,
          address: value.address,
          lat: Number(value.lat),
          lng: Number(value.lng),
        },
      );
      setApproving(null);
      load();
      refreshPendingCount();
      toast('Точка добавлена на карту');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const reject = async () => {
    if (!rejecting) return;
    try {
      await api.post(`/admin/restaurant-suggestions/${rejecting.id}/reject`, {
        moderator_comment: rejectComment,
        is_spam: rejectSpam,
      });
      setRejecting(null);
      setRejectComment('');
      setRejectSpam(false);
      load();
      refreshPendingCount();
      toast('Заявка отклонена');
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  return (
    <div>
      <h1>Заявки на рестораны</h1>
      <div className="admin-toolbar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="pending">Ожидают</option>
          <option value="approved">Одобренные</option>
          <option value="rejected">Отклонённые</option>
          <option value="">Все</option>
        </select>
      </div>

      {groups.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="inbox" size={44} strokeWidth={1.4} /></div>
          <div>Заявок нет</div>
        </div>
      )}

      {groups.map((g) => (
        <CollapsibleGroup
          key={g.brand_id}
          title={g.brand_name}
          color={g.brand_color}
          count={g.suggestions.length}
        >
          <div className="suggestion-group">
          {g.suggestions.map((s) => {
            const label = STATUS_LABELS[s.status];
            return (
              <div className="suggestion-card" key={s.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>
                    {s.city}, {s.address}
                    {s.title && ` (${s.title})`}
                  </strong>
                  <span className={`tag ${label.cls}`}>{label.text}</span>
                </div>
                {s.comment && <div>{s.comment}</div>}
                <div className="meta">
                  Координаты: {s.lat.toFixed(5)}, {s.lng.toFixed(5)} · От{' '}
                  {s.user.display_name} ({s.user.phone}) · {formatDateTime(s.created_at)}
                </div>
                {s.moderator_comment && (
                  <div className="meta">Комментарий: {s.moderator_comment}</div>
                )}
                {s.status === 'pending' && (
                  <div className="actions">
                    <button
                      className="btn btn-primary btn-small"
                      onClick={() => openApprove(s)}
                    >
                      Одобрить
                    </button>
                    <button
                      className="btn btn-danger btn-small"
                      onClick={() => {
                        setRejectComment('');
                        setRejectSpam(false);
                        setRejecting(s);
                      }}
                    >
                      Отклонить
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          </div>
        </CollapsibleGroup>
      ))}

      {approving && (
        <div className="modal-overlay" onClick={() => setApproving(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>Добавить точку по заявке</h2>
                <div className="subtitle">
                  Проверьте адрес и координаты — данные подтянуты из заявки
                </div>
              </div>
              <button className="modal-close" onClick={() => setApproving(null)}>
                <Icon name="close" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <RestaurantForm
                brands={brands}
                initial={approving.initial}
                submitLabel="Одобрить и добавить точку"
                onSubmit={approve}
                error={error}
              />
            </div>
          </div>
        </div>
      )}

      {rejecting && (
        <div className="modal-overlay" onClick={() => setRejecting(null)}>
          <div
            className="admin-modal"
            style={{ maxWidth: 480 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h2>Отклонить заявку</h2>
              <button className="modal-close" onClick={() => setRejecting(null)}>
                <Icon name="close" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="field">
                <label>Комментарий для автора (обязательно)</label>
                <textarea
                  rows={3}
                  value={rejectComment}
                  onChange={(e) => setRejectComment(e.target.value)}
                  placeholder="Например: такая точка уже есть на карте"
                />
              </div>
              <div className="field">
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={rejectSpam}
                    onChange={(e) => setRejectSpam(e.target.checked)}
                    style={{ width: 'auto' }}
                  />
                  Выдумка / спам — оштрафовать автора в рейтинге (−10)
                </label>
                <div className="hint">Дубликат существующей точки не штрафуем</div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-danger btn-block"
                disabled={!rejectComment.trim()}
                onClick={reject}
              >
                Отклонить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
