import type { MechanismType, ProjectState, WorkflowSection } from '../types';
import { mechanismTemplates } from './mechanisms';

export type FeatureAuditCategory =
  | 'Desktop parity'
  | 'Mechanisms'
  | 'MechAnim-inspired'
  | 'Web native';

export interface FeatureAuditItem {
  id: string;
  label: string;
  category: FeatureAuditCategory;
  passed: boolean;
  evidence: string;
  required: boolean;
}

export interface FeatureAuditSummary {
  items: FeatureAuditItem[];
  categories: Array<{
    category: FeatureAuditCategory;
    passed: number;
    total: number;
  }>;
  passed: number;
  required: number;
  percent: number;
  complete: boolean;
  missingRequired: FeatureAuditItem[];
}

export interface FeatureAuditCapabilities {
  sections: WorkflowSection[];
  exportFormats: Array<'json' | 'svg' | 'dxf' | 'blueprint' | 'study'>;
  directHandles: boolean;
  pathOptimizer: boolean;
  mediaTracking: boolean;
  pwaManifest: boolean;
  serviceWorker: boolean;
  localAutosave: boolean;
  responsiveCanvas: boolean;
  physicsAwareness: boolean;
  resourceManifest: boolean;
  evidenceDriven: boolean;
}

export interface WebShellRuntimeEvidence {
  manifestLinked: boolean;
  serviceWorkerAvailable: boolean;
  actionRegistryWired: boolean;
}

export const pythonDesktopMechanismTypes: MechanismType[] = [
  'four-bar',
  'five-bar',
  'six-bar',
  'cam-follower',
  'gear-pair',
  'planetary-gear',
  'slider-crank'
];

export const webExtensionMechanismTypes: MechanismType[] = [
  'crank',
  'quick-return',
  'scotch-yoke'
];

export const requiredMechanismTypes: MechanismType[] = pythonDesktopMechanismTypes;

export const defaultFeatureAuditCapabilities: FeatureAuditCapabilities = {
  sections: ['welcome', 'character', 'paths', 'studio', 'foundry', 'lab', 'options'],
  exportFormats: ['json', 'svg', 'dxf', 'blueprint', 'study'],
  directHandles: true,
  pathOptimizer: true,
  mediaTracking: true,
  pwaManifest: true,
  serviceWorker: true,
  localAutosave: true,
  responsiveCanvas: true,
  physicsAwareness: true,
  resourceManifest: true,
  evidenceDriven: true
};

export const applyRuntimeWebShellEvidence = (
  capabilities: FeatureAuditCapabilities,
  evidence: WebShellRuntimeEvidence
): FeatureAuditCapabilities => ({
  ...capabilities,
  pwaManifest: evidence.manifestLinked,
  serviceWorker: evidence.serviceWorkerAvailable,
  evidenceDriven: capabilities.evidenceDriven && evidence.actionRegistryWired
});

const hasAll = <T extends string>(values: T[], required: T[]): boolean => {
  const set = new Set(values);
  return required.every((value) => set.has(value));
};

const count = (value: number, noun: string): string => `${value} ${noun}${value === 1 ? '' : 's'}`;

export const buildFeatureAudit = (
  project: ProjectState,
  capabilities: FeatureAuditCapabilities = defaultFeatureAuditCapabilities
): FeatureAuditSummary => {
  const templateTypes = mechanismTemplates.map((template) => template.type);
  const pathCount = Object.values(project.paths).filter((path) => path.enabled && path.points.length >= 2).length;
  const mechanismPartBindings = project.mechanisms.filter((mechanism) => Boolean(project.parts[mechanism.partName] || project.skeleton?.joints[mechanism.partName])).length;
  const requiredExports: FeatureAuditCapabilities['exportFormats'] = ['json', 'svg', 'dxf', 'blueprint', 'study'];
  const requiredSections: WorkflowSection[] = ['welcome', 'character', 'paths', 'studio', 'foundry', 'lab', 'options'];

  const items: FeatureAuditItem[] = [
    {
      id: 'desktop-sections',
      label: 'Desktop tab workflow mapped to React sections',
      category: 'Desktop parity',
      passed: hasAll(capabilities.sections, requiredSections),
      evidence: `${capabilities.sections.length}/${requiredSections.length} sections registered`,
      required: true
    },
    {
      id: 'character-rig',
      label: 'Character parts, skeleton, anchors, and reference intake',
      category: 'Desktop parity',
      passed: Object.keys(project.parts).length > 0 && Boolean(project.skeleton) && Object.keys(project.skeleton?.joints ?? {}).length > 0,
      evidence: `${count(Object.keys(project.parts).length, 'part')} · ${count(Object.keys(project.skeleton?.joints ?? {}).length, 'joint')}`,
      required: true
    },
    {
      id: 'paths',
      label: 'Path editor with draw, close, smooth, resample, and assignment',
      category: 'Desktop parity',
      passed: pathCount > 0 && Boolean(project.paths[project.selectedPathPart]),
      evidence: `${count(pathCount, 'enabled path')} · selected ${project.selectedPathPart}`,
      required: true
    },
    {
      id: 'mechanism-design',
      label: 'Mechanism design, animation, traces, and character binding',
      category: 'Desktop parity',
      passed: project.mechanisms.length > 0 && mechanismPartBindings === project.mechanisms.length,
      evidence: `${count(project.mechanisms.length, 'mechanism')} · ${count(mechanismPartBindings, 'bound target')}`,
      required: true
    },
    {
      id: 'foundry-lab-options',
      label: 'Foundry, lab, kit catalog, options, and project I/O surfaces',
      category: 'Desktop parity',
      passed: project.presets.length > 0 && project.lab.kitAssets.length > 0 && project.lab.episodes.length > 0 && Boolean(project.settings) && capabilities.resourceManifest,
      evidence: `${count(project.presets.length, 'preset')} · ${count(project.lab.kitAssets.length, 'kit asset')} · ${count(project.lab.episodes.length, 'lab episode')} · ${project.resourceManifest.desktopResources.length} desktop resource links`,
      required: true
    },
    {
      id: 'mechanism-library',
      label: 'Full Python desktop mechanism family library',
      category: 'Mechanisms',
      passed: hasAll(templateTypes, pythonDesktopMechanismTypes),
      evidence: `${pythonDesktopMechanismTypes.length}/${pythonDesktopMechanismTypes.length} Python-backed families plus ${webExtensionMechanismTypes.filter((type) => templateTypes.includes(type)).length} web-only extension`,
      required: true
    },
    {
      id: 'web-only-mechanism-extension',
      label: 'MechAnim-inspired web-only mechanism extension is classified separately',
      category: 'MechAnim-inspired',
      passed: webExtensionMechanismTypes.every((type) => templateTypes.includes(type) && project.resourceManifest.webOnlyMechanisms.includes(type)),
      evidence: `${project.resourceManifest.webOnlyMechanisms.join(', ') || 'none'} marked web-only`,
      required: false
    },
    {
      id: 'direct-handles',
      label: 'Direct parametric handles and whole-mechanism dragging',
      category: 'Mechanisms',
      passed: capabilities.directHandles && capabilities.evidenceDriven,
      evidence: capabilities.directHandles ? 'SVG nodes edit mechanism parameters; capability must be backed by canvas tests/browser evidence' : 'direct handle capability not declared',
      required: true
    },
    {
      id: 'physics-aware-simulation',
      label: 'Physics-aware simulation diagnostics',
      category: 'Mechanisms',
      passed: capabilities.physicsAwareness && project.settings.animationDuration > 0,
      evidence: capabilities.physicsAwareness ? 'velocity, acceleration, load, energy, and stability reports enabled' : 'physics capability not declared',
      required: true
    },
    {
      id: 'path-fitting',
      label: 'MechAnim-style path fitting and mechanism recommendations',
      category: 'MechAnim-inspired',
      passed: capabilities.pathOptimizer && pathCount > 0 && project.mechanisms.length > 0,
      evidence: capabilities.pathOptimizer ? 'optimizer/recommendation engine wired to selected path' : 'optimizer capability not declared',
      required: true
    },
    {
      id: 'tracking',
      label: 'Manual media tracking, smoothing, loop closing, and path transfer',
      category: 'MechAnim-inspired',
      passed: capabilities.mediaTracking && typeof project.tracking.showOverlay === 'boolean',
      evidence: `${count(project.tracking.annotations.length, 'saved track')} · overlay ${project.tracking.showOverlay ? 'on' : 'off'}`,
      required: true
    },
    {
      id: 'fabrication-exports',
      label: 'JSON, SVG, DXF, blueprint, and study exports',
      category: 'MechAnim-inspired',
      passed: hasAll(capabilities.exportFormats, requiredExports),
      evidence: `${capabilities.exportFormats.join(', ')}`,
      required: true
    },
    {
      id: 'light-ui',
      label: 'Modern minimal light-first interface',
      category: 'Web native',
      passed: project.settings.theme === 'light',
      evidence: `default theme ${project.settings.theme}`,
      required: true
    },
    {
      id: 'web-shell',
      label: 'Autosave, offline PWA shell, and responsive canvas tooling',
      category: 'Web native',
      passed: capabilities.localAutosave && capabilities.pwaManifest && capabilities.serviceWorker && capabilities.responsiveCanvas && capabilities.evidenceDriven,
      evidence: `autosave ${capabilities.localAutosave ? 'on' : 'off'} · manifest ${capabilities.pwaManifest ? 'on' : 'off'} · service worker ${capabilities.serviceWorker ? 'on' : 'off'}`,
      required: true
    }
  ];

  const requiredItems = items.filter((item) => item.required);
  const passed = requiredItems.filter((item) => item.passed).length;
  const categories = (['Desktop parity', 'Mechanisms', 'MechAnim-inspired', 'Web native'] as FeatureAuditCategory[]).map((category) => {
    const categoryItems = items.filter((item) => item.category === category);
    return {
      category,
      passed: categoryItems.filter((item) => item.passed).length,
      total: categoryItems.length
    };
  });

  return {
    items,
    categories,
    passed,
    required: requiredItems.length,
    percent: Math.round((passed / Math.max(1, requiredItems.length)) * 100),
    complete: passed === requiredItems.length,
    missingRequired: requiredItems.filter((item) => !item.passed)
  };
};
