export type AppActionId =
  | 'playPause'
  | 'importProject'
  | 'saveJson'
  | 'exportSvg'
  | 'exportBlueprint'
  | 'exportDxf'
  | 'exportStudy'
  | 'resetView'
  | 'undo'
  | 'redo';

export interface AppActionDefinition {
  id: AppActionId;
  label: string;
  shortcut?: string;
  scope: 'project' | 'view' | 'export' | 'playback';
  projectMutating: boolean;
}

export const appActionDefinitions: AppActionDefinition[] = [
  { id: 'playPause', label: 'Play / pause', shortcut: 'Space', scope: 'playback', projectMutating: false },
  { id: 'importProject', label: 'Import project', shortcut: 'Ctrl+O', scope: 'project', projectMutating: true },
  { id: 'saveJson', label: 'Save JSON', shortcut: 'Ctrl+S', scope: 'export', projectMutating: false },
  { id: 'exportSvg', label: 'Export SVG', scope: 'export', projectMutating: false },
  { id: 'exportBlueprint', label: 'Export blueprint', shortcut: 'Ctrl+B', scope: 'export', projectMutating: false },
  { id: 'exportDxf', label: 'Export DXF', scope: 'export', projectMutating: false },
  { id: 'exportStudy', label: 'Export study bundle', scope: 'export', projectMutating: false },
  { id: 'resetView', label: 'Reset view', shortcut: 'Ctrl+0', scope: 'view', projectMutating: true },
  { id: 'undo', label: 'Undo project edit', shortcut: 'Ctrl+Z', scope: 'project', projectMutating: true },
  { id: 'redo', label: 'Redo project edit', shortcut: 'Ctrl+Y', scope: 'project', projectMutating: true }
];

export interface KeyboardLike {
  code?: string;
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

export const isEditableTarget = (target: EventTarget | null): boolean => {
  const element = target as HTMLElement | null;
  return element?.tagName === 'INPUT'
    || element?.tagName === 'TEXTAREA'
    || element?.tagName === 'SELECT'
    || element?.isContentEditable === true;
};

export const actionForKeyboardEvent = (event: KeyboardLike): AppActionId | undefined => {
  const key = event.key.toLowerCase();
  const chord = Boolean(event.ctrlKey || event.metaKey);
  if (event.code === 'Space' || event.key === ' ') return 'playPause';
  if (!chord) return undefined;
  if (key === 's') return 'saveJson';
  if (key === 'o') return 'importProject';
  if (key === 'b') return 'exportBlueprint';
  if (event.key === '0') return 'resetView';
  if (key === 'z') return event.shiftKey ? 'redo' : 'undo';
  if (key === 'y') return 'redo';
  return undefined;
};

export const enabledActionIds = (availability: Partial<Record<AppActionId, boolean>>): AppActionId[] =>
  appActionDefinitions
    .filter((action) => availability[action.id] ?? true)
    .map((action) => action.id);
