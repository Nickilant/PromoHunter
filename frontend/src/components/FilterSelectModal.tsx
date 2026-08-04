import { useMemo, useState } from 'react';

import { useDismiss } from '../hooks/useDismiss';
import Icon from './Icon';
import type { IconName } from './Icon';
import Overlay from './Overlay';

export interface FilterSelectOption {
  value: string;
  label: string;
  tone?: string;
}

interface Props {
  title: string;
  subtitle: string;
  icon: IconName;
  options: FilterSelectOption[];
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
}

export default function FilterSelectModal({
  title,
  subtitle,
  icon,
  options,
  value,
  onChange,
  onClose,
}: Props) {
  const [query, setQuery] = useState('');
  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);
  const shown = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('ru');
    return normalized
      ? options.filter((option) => option.label.toLocaleLowerCase('ru').includes(normalized))
      : options;
  }, [options, query]);

  const select = (nextValue: string) => {
    onChange(nextValue);
    dismiss();
  };

  return (
    <Overlay>
      <div
        className={`modal-overlay${closing ? ' closing' : ''}`}
        onMouseDown={(event) => event.target === event.currentTarget && dismiss()}
        onAnimationEnd={onAnimationEnd}
      >
        <div
          className={`modal filter-select-modal${closing ? ' closing' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="filter-select-title"
        >
          <div className="modal-head">
            <div>
              <h2 id="filter-select-title">{title}</h2>
              <div className="subtitle">{subtitle}</div>
            </div>
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          </div>

          <div className="filter-select-search">
            <Icon name="search" size={18} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Начните вводить название…"
              aria-label={`Поиск: ${title.toLocaleLowerCase('ru')}`}
              autoFocus
            />
            {query && (
              <button onClick={() => setQuery('')} aria-label="Очистить поиск">
                <Icon name="close" size={16} />
              </button>
            )}
          </div>

          <div className="filter-select-list" role="listbox" aria-label={title}>
            {shown.map((option) => {
              const selected = option.value === value;
              return (
                <button
                  key={option.value || 'all'}
                  className={selected ? 'selected' : ''}
                  onClick={() => select(option.value)}
                  role="option"
                  aria-selected={selected}
                >
                  <span className="filter-select-option-icon">
                    {option.tone ? (
                      <span className={`filter-status-dot ${option.tone}`} />
                    ) : (
                      <Icon name={icon} size={17} />
                    )}
                  </span>
                  <span className="filter-select-option-label">{option.label}</span>
                  <span className="filter-select-check">
                    {selected && <Icon name="check" size={17} strokeWidth={2.2} />}
                  </span>
                </button>
              );
            })}
            {shown.length === 0 && (
              <div className="filter-select-empty">
                <Icon name="search" size={28} />
                <span>Ничего не найдено</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </Overlay>
  );
}
