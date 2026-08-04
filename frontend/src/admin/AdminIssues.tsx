import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { api } from '../api/client';
import Icon from '../components/Icon';
import { useToast } from '../components/Toast';
import type { AdminDataIssue, IssueStatus } from '../types';
import { formatDateTime } from '../utils/time';
import type { AdminOutletContext } from './AdminLayout';
import AdminSearch, { matches } from './AdminSearch';

const TYPE_LABELS: Record<string, string> = {
  closed: 'Ресторан закрыт', temporarily_closed: 'Временно не работает', wrong_address: 'Неверный адрес',
  wrong_location: 'Неверная точка на карте', duplicate: 'Дубликат', moved: 'Ресторан переехал',
  promotion_ended: 'Акция закончилась', promotion_wrong: 'Ошибка в акции', other: 'Другая ошибка',
};
const STATUS_LABELS: Record<IssueStatus, { text: string; cls: string }> = {
  pending: { text: 'Ожидает', cls: 'warn' }, resolved: { text: 'Исправлено', cls: 'ok' }, rejected: { text: 'Отклонено', cls: 'error' },
};

export default function AdminIssues() {
  const [issues, setIssues] = useState<AdminDataIssue[]>([]);
  const [statusFilter, setStatusFilter] = useState<IssueStatus | ''>('pending');
  const [query, setQuery] = useState('');
  const [reviewing, setReviewing] = useState<{ issue: AdminDataIssue; status: 'resolved' | 'rejected' } | null>(null);
  const [comment, setComment] = useState('');
  const { refreshPendingCount } = useOutletContext<AdminOutletContext>();
  const toast = useToast();
  const load = () => api.get<AdminDataIssue[]>(`/admin/issues${statusFilter ? `?status=${statusFilter}` : ''}`).then(setIssues).catch(() => setIssues([]));
  useEffect(() => { void load(); }, [statusFilter]);
  const shown = issues.filter((issue) => matches(query, TYPE_LABELS[issue.type], issue.details, issue.restaurant.address, issue.restaurant.brand.name, issue.promotion_title, issue.user.display_name));
  const review = async () => {
    if (!reviewing) return;
    try {
      await api.post(`/admin/issues/${reviewing.issue.id}/review`, { status: reviewing.status, moderator_comment: comment || null });
      setReviewing(null); setComment(''); load(); refreshPendingCount(); toast(reviewing.status === 'resolved' ? 'Сообщение отмечено исправленным' : 'Сообщение отклонено');
    } catch (err) { toast(err instanceof Error ? err.message : 'Ошибка'); }
  };
  return <div>
    <h1>Ошибки в данных</h1>
    <div className="admin-toolbar"><select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as IssueStatus | '')}><option value="pending">Ожидают</option><option value="resolved">Исправленные</option><option value="rejected">Отклонённые</option><option value="">Все</option></select></div>
    <AdminSearch value={query} onChange={setQuery} placeholder="Поиск по точке, сети, автору или описанию" found={shown.length} total={issues.length} />
    {shown.length === 0 && <div className="empty-state"><div className="big"><Icon name="inbox" size={44} /></div><div>Сообщений нет</div></div>}
    <div className="suggestion-group">{shown.map((issue) => { const label = STATUS_LABELS[issue.status]; return <div className="suggestion-card" key={issue.id}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong>{TYPE_LABELS[issue.type] ?? issue.type}</strong><span className={`tag ${label.cls}`}>{label.text}</span></div>
      <div>{issue.restaurant.brand.name} · {issue.restaurant.city}, {issue.restaurant.address}</div>
      {issue.promotion_title && <div className="meta">Акция: {issue.promotion_title}</div>}
      <div>{issue.details}</div><div className="meta">От {issue.user.display_name} ({issue.user.phone}) · {formatDateTime(issue.created_at)}</div>
      {issue.moderator_comment && <div className="meta">Комментарий: {issue.moderator_comment}</div>}
      {issue.status === 'pending' && <div className="actions"><button className="btn btn-primary btn-small" onClick={() => setReviewing({ issue, status: 'resolved' })}>Исправлено</button><button className="btn btn-danger btn-small" onClick={() => setReviewing({ issue, status: 'rejected' })}>Отклонить</button></div>}
    </div>; })}</div>
    {reviewing && <div className="modal-overlay" onClick={() => setReviewing(null)}><div className="admin-modal" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}><div className="modal-head"><h2>{reviewing.status === 'resolved' ? 'Подтвердить исправление' : 'Отклонить сообщение'}</h2><button className="modal-close" onClick={() => setReviewing(null)}><Icon name="close" size={20} /></button></div><div className="modal-body"><div className="field"><label>Комментарий пользователю</label><textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} /></div></div><div className="modal-footer"><button className={`btn btn-block ${reviewing.status === 'resolved' ? 'btn-primary' : 'btn-danger'}`} onClick={review}>Сохранить решение</button></div></div></div>}
  </div>;
}
