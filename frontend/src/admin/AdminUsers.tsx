import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useToast } from '../components/Toast';
import { useAuth } from '../hooks/useAuth';
import type { AdminUser, Role } from '../types';
import { formatDate } from '../utils/time';

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const { user: me } = useAuth();
  const toast = useToast();

  const load = () => {
    api.get<AdminUser[]>('/admin/users').then(setUsers).catch(() => {});
  };

  useEffect(load, []);

  const patch = async (id: number, body: { role?: Role; is_blocked?: boolean }) => {
    try {
      await api.patch(`/admin/users/${id}`, body);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  return (
    <div>
      <h1>Пользователи</h1>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Имя</th>
              <th>Роль</th>
              <th>Статус</th>
              <th>Регистрация</th>
              <th>Отчётов</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = me?.id === u.id;
              return (
                <tr key={u.id}>
                  <td>
                    {u.email}
                    {isSelf && ' (вы)'}
                  </td>
                  <td>{u.display_name}</td>
                  <td>
                    <select
                      value={u.role}
                      disabled={isSelf}
                      onChange={(e) => patch(u.id, { role: e.target.value as Role })}
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <span className={`tag ${u.is_blocked ? 'error' : 'ok'}`}>
                      {u.is_blocked ? 'Заблокирован' : 'Активен'}
                    </span>
                  </td>
                  <td>{formatDate(u.created_at)}</td>
                  <td>{u.reports_count}</td>
                  <td>
                    <div className="actions">
                      <button
                        className={`btn btn-small ${u.is_blocked ? 'btn-ghost' : 'btn-danger'}`}
                        disabled={isSelf}
                        onClick={() => patch(u.id, { is_blocked: !u.is_blocked })}
                      >
                        {u.is_blocked ? 'Разблокировать' : 'Заблокировать'}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
