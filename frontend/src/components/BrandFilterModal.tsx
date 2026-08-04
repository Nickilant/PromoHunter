import { useMemo, useState } from 'react';

import { useDismiss } from '../hooks/useDismiss';
import type { BrandShort } from '../types';
import Icon from './Icon';
import Overlay from './Overlay';

interface Props {
  brands: BrandShort[];
  selectedIds: Set<number>;
  onApply: (ids: Set<number>) => void;
  onClose: () => void;
}

export default function BrandFilterModal({ brands, selectedIds, onApply, onClose }: Props) {
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState(() => new Set(selectedIds));
  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);
  const visibleBrands = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('ru');
    return normalized
      ? brands.filter((brand) => brand.name.toLocaleLowerCase('ru').includes(normalized))
      : brands;
  }, [brands, query]);

  const toggle = (id: number) => {
    setDraft((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Overlay>
      <div
        className={`modal-overlay${closing ? ' closing' : ''}`}
        onMouseDown={(event) => event.target === event.currentTarget && dismiss()}
        onAnimationEnd={onAnimationEnd}
      >
        <div className={`modal brand-filter-modal${closing ? ' closing' : ''}`} role="dialog" aria-modal="true" aria-labelledby="brand-filter-title">
          <div className="modal-head">
            <div>
              <h2 id="brand-filter-title">Рестораны на карте</h2>
              <div className="subtitle">
                {draft.size === 0 ? 'Показываются все сети' : `Выбрано сетей: ${draft.size}`}
              </div>
            </div>
            <button className="modal-close" onClick={dismiss} aria-label="Закрыть">
              <Icon name="close" size={20} />
            </button>
          </div>

          <div className="modal-body">
            <div className="brand-filter-search">
              <Icon name="search" size={18} />
              <input
                type="search"
                placeholder="Найти сеть…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                autoFocus
              />
            </div>

            {visibleBrands.length > 0 ? (
              <div className="brand-grid brand-filter-grid">
                {visibleBrands.map((brand) => {
                  const selected = draft.has(brand.id);
                  return (
                    <button
                      key={brand.id}
                      className={`brand-tile brand-filter-tile${selected ? ' selected' : ''}`}
                      onClick={() => toggle(brand.id)}
                      aria-pressed={selected}
                    >
                      <span className="brand-tile-avatar" style={{ background: brand.color }}>
                        {brand.name[0]}
                      </span>
                      <span className="brand-tile-name">{brand.name}</span>
                      {selected && <span className="brand-filter-check"><Icon name="check" size={14} /></span>}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state brand-filter-empty">Такой сети не нашлось</div>
            )}
          </div>

          <div className="modal-footer brand-filter-actions">
            <button className="btn btn-ghost" onClick={() => setDraft(new Set())} disabled={draft.size === 0}>
              Сбросить
            </button>
            <button className="btn btn-primary" onClick={() => { onApply(draft); onClose(); }}>
              Показать
            </button>
          </div>
        </div>
      </div>
    </Overlay>
  );
}
