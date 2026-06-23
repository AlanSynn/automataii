import type { ProjectState } from '../types';

export interface ProjectCommand {
  id: string;
  label: string;
  timestamp: string;
  projectOnly: true;
}

export interface ProjectHistory {
  present: ProjectState;
  past: Array<{ project: ProjectState; command: ProjectCommand }>;
  future: Array<{ project: ProjectState; command: ProjectCommand }>;
  limit: number;
}

const DEFAULT_LIMIT = 80;

const command = (label: string): ProjectCommand => ({
  id: `cmd-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
  label,
  timestamp: new Date().toISOString(),
  projectOnly: true
});

export const createProjectHistory = (
  initialProject: ProjectState,
  limit = DEFAULT_LIMIT
): ProjectHistory => ({
  present: initialProject,
  past: [],
  future: [],
  limit: Math.max(1, Math.min(500, Math.round(limit)))
});

export const replaceProjectHistoryRoot = (
  history: ProjectHistory,
  nextProject: ProjectState
): ProjectHistory => createProjectHistory(nextProject, history.limit);

export const canUndoProject = (history: ProjectHistory): boolean => history.past.length > 0;
export const canRedoProject = (history: ProjectHistory): boolean => history.future.length > 0;

export const commitProjectCommand = (
  history: ProjectHistory,
  label: string,
  nextProject: ProjectState
): ProjectHistory => {
  if (Object.is(history.present, nextProject)) return history;
  return {
    ...history,
    present: nextProject,
    past: [...history.past, { project: history.present, command: command(label) }].slice(-history.limit),
    future: []
  };
};

export const undoProjectHistory = (history: ProjectHistory): ProjectHistory => {
  const previous = history.past.at(-1);
  if (!previous) return history;
  return {
    ...history,
    present: previous.project,
    past: history.past.slice(0, -1),
    future: [{ project: history.present, command: previous.command }, ...history.future].slice(0, history.limit)
  };
};

export const redoProjectHistory = (history: ProjectHistory): ProjectHistory => {
  const next = history.future[0];
  if (!next) return history;
  return {
    ...history,
    present: next.project,
    past: [...history.past, { project: history.present, command: next.command }].slice(-history.limit),
    future: history.future.slice(1)
  };
};

export const historySummary = (history: ProjectHistory): string =>
  `${history.past.length} undo · ${history.future.length} redo`;
