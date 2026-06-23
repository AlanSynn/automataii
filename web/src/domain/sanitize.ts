export const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

export const safeString = (value: unknown, fallback = ''): string => {
  return typeof value === 'string' ? value : fallback;
};

export const safeText = (value: unknown, fallback = '', maxLength = 160): string => {
  const text = safeString(value, fallback)
    .replace(/[<>]/g, '')
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return (text || fallback).slice(0, maxLength);
};

export const safeBoolean = (value: unknown, fallback = false): boolean => {
  return typeof value === 'boolean' ? value : fallback;
};

export const safeNumber = (value: unknown, fallback = 0, min = -Number.MAX_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER): number => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.max(min, Math.min(max, numeric));
};

export const safeInteger = (value: unknown, fallback = 0, min = -Number.MAX_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER): number => {
  return Math.round(safeNumber(value, fallback, min, max));
};

const cssHexColor = /^#(?:[\da-f]{3}|[\da-f]{4}|[\da-f]{6}|[\da-f]{8})$/i;
const cssRgbColor = /^rgba?\(\s*(25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(25[0-5]|2[0-4]\d|1?\d?\d)(?:\s*,\s*(0|1|0?\.\d+))?\s*\)$/i;

export const safeColor = (value: unknown, fallback = '#38bdf8'): string => {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (cssHexColor.test(trimmed) || cssRgbColor.test(trimmed)) return trimmed;
  return fallback;
};

export const colorWithAlpha = (value: unknown, fallback = '#38bdf8', alpha = '22'): string => {
  const color = safeColor(value, fallback);
  if (/^#[\da-f]{6}$/i.test(color)) return `${color}${alpha}`;
  return color;
};

export const finiteNumberRecord = (value: unknown): Record<string, number> => {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value)
      .map(([key, raw]) => [key, Number(raw)] as const)
      .filter(([, raw]) => Number.isFinite(raw))
  );
};
