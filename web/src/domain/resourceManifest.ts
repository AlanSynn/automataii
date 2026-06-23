import type { MechanismType, ProjectState } from '../types';

export interface ResourceManifestEntry {
  id: string;
  desktopPath: string;
  webFamily: string;
  mechanismTypes: MechanismType[];
  status: 'web-backed' | 'web-only' | 'desktop-only';
  rationale: string;
}

export const resourceManifestEntries: ResourceManifestEntry[] = [
  {
    id: 'mechanism-content-four-bar',
    desktopPath: 'resources/mechanism_content/four_bar.json',
    webFamily: 'linkage',
    mechanismTypes: ['four-bar'],
    status: 'web-backed',
    rationale: 'Four-bar content maps to the web linkage template and Python-shaped linkages/bar_count import.'
  },
  {
    id: 'mechanism-content-five-bar',
    desktopPath: 'resources/mechanism_content/linkage_five_bar.json',
    webFamily: 'linkage',
    mechanismTypes: ['five-bar'],
    status: 'web-backed',
    rationale: 'Five-bar content maps to the web floating-chain template and closure safety metadata.'
  },
  {
    id: 'mechanism-content-six-bar',
    desktopPath: 'resources/mechanism_content/linkage_six_bar.json',
    webFamily: 'linkage',
    mechanismTypes: ['six-bar'],
    status: 'web-backed',
    rationale: 'Six-bar content maps to the web rocker extension template and Python bar_count=6 import.'
  },
  {
    id: 'mechanism-content-cam',
    desktopPath: 'resources/mechanism_content/cam_follower.json',
    webFamily: 'cam',
    mechanismTypes: ['cam-follower'],
    status: 'web-backed',
    rationale: 'Cam/follower content maps to the browser cam profile and follower force metadata.'
  },
  {
    id: 'mechanism-content-gear',
    desktopPath: 'resources/mechanism_content/gear_train.json',
    webFamily: 'gear',
    mechanismTypes: ['gear-pair', 'planetary-gear'],
    status: 'web-backed',
    rationale: 'Desktop gear content is presentation/resource-backed; web keeps gear solvers as browser-native domain previews.'
  },
  {
    id: 'mechanism-content-slider',
    desktopPath: 'resources/mechanism_content/slider_crank.json',
    webFamily: 'linear',
    mechanismTypes: ['slider-crank'],
    status: 'web-backed',
    rationale: 'Slider-crank content maps to the web piston/rail model and MechAnim-inspired path fitting.'
  },
  {
    id: 'crank-web',
    desktopPath: 'MechAnim-inspired browser primitive',
    webFamily: 'rotary',
    mechanismTypes: ['crank'],
    status: 'web-only',
    rationale: 'Basic crank is preserved for MechAnim code-level parity; desktop use is normally covered by linkage/gear workflows.'
  },
  {
    id: 'scotch-yoke-web',
    desktopPath: 'MechAnim-inspired browser primitive',
    webFamily: 'linear',
    mechanismTypes: ['scotch-yoke'],
    status: 'web-only',
    rationale: 'Scotch yoke is a web-native MechAnim-inspired addition; no Python domain resource exists yet.'
  },
  {
    id: 'quick-return-web',
    desktopPath: 'MechAnim-inspired browser primitive',
    webFamily: 'linear',
    mechanismTypes: ['quick-return'],
    status: 'web-only',
    rationale: 'Quick-return/slotted-crank is preserved for MechAnim code-level parity; no Python domain resource exists yet.'
  }
];

export const defaultResourceManifestState = (): ProjectState['resourceManifest'] => ({
  checkedAt: new Date().toISOString(),
  desktopResources: resourceManifestEntries
    .filter((entry) => entry.status !== 'web-only')
    .map((entry) => entry.desktopPath),
  webResourceFamilies: [...new Set(resourceManifestEntries.map((entry) => entry.webFamily))],
  webOnlyMechanisms: resourceManifestEntries
    .filter((entry) => entry.status === 'web-only')
    .flatMap((entry) => entry.mechanismTypes)
});

export const mechanismResourceStatus = (type: MechanismType): ResourceManifestEntry | undefined =>
  resourceManifestEntries.find((entry) => entry.mechanismTypes.includes(type));
