// @vitest-environment jsdom

import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

const AUTOSAVE_KEY = 'automataii-web-autosave-v1';
const RECOVERY_KEY = `${AUTOSAVE_KEY}:recovery`;

describe('autosave recovery guard', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it('does not overwrite a corrupted saved workspace until the user opts in', async () => {
    const original = '{bad saved workspace';
    window.localStorage.setItem(AUTOSAVE_KEY, original);

    render(<App />);
    await act(async () => {
      vi.advanceTimersByTime(400);
    });

    expect(window.localStorage.getItem(AUTOSAVE_KEY)).toBe(original);
    expect(window.localStorage.getItem(RECOVERY_KEY)).toBe(original);
    expect(screen.getByText(/Autosave recovery paused/i)).toBeTruthy();
  });
});
