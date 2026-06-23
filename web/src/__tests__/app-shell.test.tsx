// @vitest-environment jsdom
import { renderToString } from 'react-dom/server';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '../App';

describe('React app shell workflow coverage', () => {
  it('server-renders every primary workflow section and launch affordance', () => {
    const html = renderToString(<App />);
    const normalized = html.replace(/<!-- -->/g, '');

    [
      'Native Web Studio',
      'Welcome',
      'Character Selection',
      'Path Editor',
      'Mechanism Design',
      'Mechanism Foundry',
      'Lab',
      'Options',
      'Automataii Web Studio',
      'Feature integration audit',
      'All required workflows integrated',
      '13/13 required checks pass',
      'Physics 97%',
      'Start character',
      'Open foundry',
      'Import',
      'JSON',
      'SVG',
      'Blueprint',
      'DXF',
      'Study'
    ].forEach((label) => expect(normalized).toContain(label));
  });

  it('server-rendered shell stays light-first and free of unsafe inline script output', () => {
    const html = renderToString(<App />);
    const normalized = html.replace(/<!-- -->/g, '');
    const unsafeSinkName = ['dangerously', 'SetInnerHTML'].join('');

    expect(normalized).toContain('Full React migration');
    expect(normalized).toContain('Light-first UI');
    expect(normalized).toContain('Offline-ready PWA');
    expect(normalized).not.toContain('<script');
    expect(normalized).not.toContain(unsafeSinkName);
  });

  it('routes shell shortcuts through project history and starts a fresh history root on reset', async () => {
    const manifest = document.createElement('link');
    manifest.rel = 'manifest';
    manifest.href = '/manifest.webmanifest';
    document.head.replaceChildren(manifest);
    Object.defineProperty(window.navigator, 'serviceWorker', {
      value: {},
      configurable: true
    });
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: 'Zoom +' }));
    await waitFor(() => expect(document.body.textContent).toContain('1 undo · 0 redo'));
    expect(document.body.textContent).toContain('118%');

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
    await waitFor(() => expect(document.body.textContent).toContain('0 undo · 1 redo'));
    expect(document.body.textContent).toContain('100%');

    fireEvent.keyDown(window, { key: 'y', ctrlKey: true });
    await waitFor(() => expect(document.body.textContent).toContain('1 undo · 0 redo'));
    expect(document.body.textContent).toContain('118%');

    fireEvent.click(screen.getByRole('button', { name: 'Options' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reset to demo project' }));
    await waitFor(() => expect(document.body.textContent).toContain('0 undo · 0 redo'));
  });
});
