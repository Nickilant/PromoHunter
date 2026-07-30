/**
 * Русские числовые формы: pluralize(2, ['точка', 'точки', 'точек']) → 'точки'.
 * Порядок форм — как в CLDR: одна, две, пять.
 */
export function pluralize(
  count: number,
  forms: readonly [string, string, string],
): string {
  const abs = Math.abs(count) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return forms[2];
  if (last === 1) return forms[0];
  if (last >= 2 && last <= 4) return forms[1];
  return forms[2];
}

export const POINTS = ['точка', 'точки', 'точек'] as const;
export const PLAYERS = ['игрок', 'игрока', 'игроков'] as const;
export const RECEIPTS = ['чек', 'чека', 'чеков'] as const;
