import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { AdminBrand, AdminSuggestion, SuggestionGroup } from '../types';
import { formatDateTime } from '../utils/time';
import type { AdminOutletContext } from './AdminLayout';
import CollapsibleGroup from './CollapsibleGroup';
import PromotionForm, { fromLocalInput, PromotionFormValue } from './PromotionForm';
import Icon from '../components/Icon';

const STATUS_LABELS: Record<string, { text: string; cls: string }> = {
  pending: { text: 'Ожидает', cls: 'warn' },
  approved: { text: 'Одобрена', cls: 'ok' },
  rejected: { text: 'Отклонена', cls: 'error' },
};

export default function AdminSuggestions() {
  const [groups, setGroups] = useState<SuggestionGroup[]>([]);
  const [brands, setBrands] = useState<AdminBrand[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [approving, setApproving] = useState<{
    suggestion: AdminSuggestion;
    initial: PromotionFormValue;
  } | null>(null);
  const [rejecting, setRejecting] = useState<AdminSuggestion | null>(null);
  const [rejectComment, setRejectComment] = useState('');
  const [rejectSpam, setRejectSpam] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { refreshPendingCount } = useOutletContext<AdminOutletContext>();
  const toast = useToast();

  const load = () => {
    const params = statusFilter ? `?status=${statusFilter}` : '';
    api
      .get<SuggestionGroup[]>(`/admin/suggestions${params}`)
      .then(setGroups)
      .catch(() => {});
  };

  useEffect(() => {
    api.get<AdminBrand[]>('/admin/brands').then(setBrands).catch(() => {});
  }, []);

  useEffect(load, [statusFilter]);

  const openApprove = (s: AdminSuggestion) => {
    setError(null);
    setApproving({
      suggestion: s,
      initial: {
        brand_id: s.brand_id !== null ? String(s.brand_id) : '',
        title: s.title,
        description: s.description ?? '',
        starts_at: '',
        ends_at: '',
        is_active: true,
        items: s.items_raw
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)
          .map((name) => ({ name })),
        // Заявка пришла из конкретного города — предлагаем сузить охват до
        // него, чтобы одобрение локальной заявки не стало федеральной акцией
        scope: s.city
          ? { mode: 'include' as const, cities: [s.city] }
          : { mode: 'exclude' as const, cities: [] },
      },
    });
  };

  const approve = async (value: PromotionFormValue) => {
    if (!approving) return;
    setError(null);
    try {
      await api.post(`/admin/suggestions/${approving.suggestion.id}/approve`, {
        brand_id: Number(value.brand_id),
        title: value.title,
        description: value.description || null,
        starts_at: fromLocalInput(value.starts_at),
        ends_at: fromLocalInput(value.ends_at),
        items: value.items.map((i) => i.name).filter(Boolean),
        scope: value.scope,
      });
      setApproving(null);
      load();
      refreshPendingCount();
      toast('Акция создана по заявке');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const reject = async () => {
    if (!rejecting) return;
    try {
      await api.post(`/admin/suggestions/${rejecting.id}/reject`, {
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
      <h1>Заявки на акции</h1>
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
          key={`${g.brand_id ?? 'raw'}-${g.brand_name}`}
          title={g.brand_name}
          color={g.brand_color}
          count={g.suggestions.length}
          badge={
            g.brand_id === null ? (
              <span className="tag warn">бренда нет в базе</span>
            ) : undefined
          }
        >
          <div className="suggestion-group">
          {g.suggestions.map((s) => {
            const label = STATUS_LABELS[s.status];
            return (
              <div className="suggestion-card" key={s.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{s.title}</strong>
                  <span className={`tag ${label.cls}`}>{label.text}</span>
                </div>
                {s.description && <div>{s.description}</div>}
                <div className="items-raw">{s.items_raw}</div>
                <div className="meta">
                  От {s.user.display_name} ({s.user.phone}) · {formatDateTime(s.created_at)}
                  {s.restaurant &&
                    ` · Замечено: ${s.restaurant.title || s.restaurant.address}`}
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
                <h2>Создать акцию по заявке</h2>
                <div className="subtitle">
                  Проверьте и поправьте данные — они подтянуты из заявки
                </div>
              </div>
              <button className="modal-close" onClick={() => setApproving(null)} aria-label="Закрыть">
                <Icon name="close" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <PromotionForm
                brands={brands}
                initial={approving.initial}
                submitLabel="Одобрить и создать акцию"
                onSubmit={approve}
                error={error}
              />
            </div>
          </div>
        </div>
      )}

      {rejecting && (
        <div className="modal-overlay" onClick={() => setRejecting(null)}>
          <div className="admin-modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h2>Отклонить заявку</h2>
              <button className="modal-close" onClick={() => setRejecting(null)} aria-label="Закрыть">
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
                  placeholder="Например: дубликат, акция уже создана"
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
                <div className="hint">
                  Обычный дубликат или неактуальную заявку не штрафуем
                </div>
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
