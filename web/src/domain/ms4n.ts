import type { KitAsset, LabEpisode, MechanismType, ProjectState } from '../types';

export const MS4N_SCHEMA_VERSION = 'ms4n-web-v1';

export interface MS4NValidatedEpisode {
  id: string;
  title: string;
  mechanismType: MechanismType | 'mixed';
  symptom: string;
  cause: string;
  repairAction: string;
  evidenceOutputs: string[];
  suggestedEvidenceOutputs: string[];
  status: LabEpisode['status'];
  traceMetrics: Record<string, number>;
  valid: boolean;
  warnings: string[];
}

export interface MS4NExportPayload {
  schema_version: typeof MS4N_SCHEMA_VERSION;
  episodes: MS4NValidatedEpisode[];
  trace_summary: {
    episode_count: number;
    valid_episode_count: number;
    mechanism_types: string[];
    warning_count: number;
  };
  kit_evidence_map: Record<string, string[]>;
  validation_warnings: string[];
}

const defaultEvidenceOutputs = (assets: KitAsset[]): string[] =>
  [...new Set(assets.flatMap((asset) => asset.evidenceOutputs))].slice(0, 4);

export const validateMS4NEpisode = (
  episode: LabEpisode,
  assets: KitAsset[],
  traceMetrics: Record<string, number> = {}
): MS4NValidatedEpisode => {
  const evidenceOutputs = (episode.evidenceOutputs ?? []).filter(Boolean);
  const suggestedEvidenceOutputs = defaultEvidenceOutputs(assets);
  const warnings = [
    episode.symptom.trim() ? '' : 'Missing symptom',
    episode.suspectedCause.trim() ? '' : 'Missing suspected cause',
    episode.repairAction.trim() ? '' : 'Missing repair action',
    evidenceOutputs.length > 0 ? '' : 'Missing evidence output'
  ].filter(Boolean);
  return {
    id: episode.id,
    title: episode.title,
    mechanismType: episode.mechanismType ?? 'mixed',
    symptom: episode.symptom,
    cause: episode.suspectedCause,
    repairAction: episode.repairAction,
    evidenceOutputs,
    suggestedEvidenceOutputs,
    status: episode.status,
    traceMetrics: { ...(episode.traceMetrics ?? {}), ...traceMetrics },
    valid: warnings.length === 0,
    warnings
  };
};

export const buildKitEvidenceMap = (assets: KitAsset[]): Record<string, string[]> =>
  Object.fromEntries(assets.map((asset) => [asset.id, asset.evidenceOutputs]));

export const buildMS4NExportPayload = (
  project: ProjectState,
  traceMetrics: Record<string, number> = {}
): MS4NExportPayload => {
  const episodes = project.lab.episodes.map((episode) => validateMS4NEpisode(episode, project.lab.kitAssets, traceMetrics));
  const mechanismTypes = [...new Set(episodes.map((episode) => episode.mechanismType))];
  const validationWarnings = episodes.flatMap((episode) => episode.warnings.map((warning) => `${episode.id}: ${warning}`));
  return {
    schema_version: MS4N_SCHEMA_VERSION,
    episodes,
    trace_summary: {
      episode_count: episodes.length,
      valid_episode_count: episodes.filter((episode) => episode.valid).length,
      mechanism_types: mechanismTypes,
      warning_count: validationWarnings.length
    },
    kit_evidence_map: buildKitEvidenceMap(project.lab.kitAssets),
    validation_warnings: validationWarnings
  };
};
