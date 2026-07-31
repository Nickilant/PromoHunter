import Icon from '../components/Icon';

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  /** Сколько строк осталось после фильтра — показываем рядом с полем */
  found?: number;
  total?: number;
}

/**
 * Поиск по разделу админки. Один компонент на все вкладки: списки растут,
 * и глазами в них уже не находится.
 */
export default function AdminSearch({
  value,
  onChange,
  placeholder,
  found,
  total,
}: Props) {
  return (
    <div className="admin-search">
      <Icon name="search" size={16} />
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && (
        <button
          className="admin-search-clear"
          onClick={() => onChange('')}
          aria-label="Очистить поиск"
        >
          <Icon name="close" size={15} />
        </button>
      )}
      {value && found !== undefined && total !== undefined && (
        <span className="admin-search-count">
          {found} из {total}
        </span>
      )}
    </div>
  );
}

/** Совпадение по любому из полей строки, без учёта регистра. */
export function matches(query: string, ...fields: (string | null | undefined)[]) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return fields.some((f) => (f ?? '').toLowerCase().includes(q));
}
