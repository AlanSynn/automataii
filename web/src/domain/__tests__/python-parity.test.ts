import { describe, expect, it } from 'vitest';
import { buildFeatureAudit, defaultFeatureAuditCapabilities } from '../parity';
import { computeMechanismState } from '../mechanisms';
import { normalizeProject, parseProjectResult } from '../project';
import { mechanismResourceStatus, resourceManifestEntries } from '../resourceManifest';

describe('Python desktop parity bridge', () => {
  it('imports unified Python linkages + bar_count without falling back to demo mechanisms', () => {
    const project = normalizeProject({
      mechanisms: {
        four: { type: 'linkages', part_name: 'right_wrist', params: { bar_count: 4, ground_link: 144 } },
        five: { mechanism_type: 'linkages', part_name: 'left_wrist', params: { bar_count: 5, coupler_length: 132 } },
        six: { type: 'unified_linkage', part_name: 'right_ankle', bar_count: 6, params: { pivot_height: 118 } }
      }
    });

    expect(project.mechanisms).toHaveLength(3);
    expect(project.mechanisms.map((mechanism) => mechanism.type)).toEqual(['four-bar', 'five-bar', 'six-bar']);
    expect(project.mechanisms[0].params.groundLink).toBe(144);
    expect(project.mechanisms[1].params.couplerLink).toBe(132);
    expect(project.mechanisms[2].params.pivotHeight).toBe(118);
    expect(project.mechanisms.every((mechanism) => mechanism.layerData?.python_import === true)).toBe(true);
  });

  it('carries Python-style safety details, render flags, and force vectors in web mechanism states', () => {
    const project = normalizeProject({
      mechanisms: {
        five: { type: 'linkages', part_name: 'right_wrist', params: { bar_count: 5, ground_link: 900, input_link: 10, output_link: 10, coupler_link: 5 } }
      }
    });
    const state = computeMechanismState(project.mechanisms[0], 0);

    expect(state.valid).toBe(false);
    expect(state.safety.level).toBe('caution');
    expect(state.safety.details?.pythonSafetyLevel).toBe('warning');
    expect(state.metadata.renderConfig).toMatchObject({ show_forces: true, show_safety_zones: true });
    expect(Object.values(state.forces ?? {}).length).toBeGreaterThan(0);
    expect(Object.values(state.forces ?? {}).every((force) => Number.isFinite(force.magnitude))).toBe(true);
  });

  it('imports Python character preset and standardized skeleton shapes', () => {
    const project = normalizeProject({
      character_preset: {
        parts: {
          upper_arm_L: {
            name: 'upper_arm_L',
            svg_path: 'parts/upper_arm_L.svg',
            anchor_joint: 'left_shoulder',
            default_transform: [-12, 8, 14]
          }
        },
        skeleton: {
          joints: {
            root: { id: 'root', name: 'Root', position: [0, 0] },
            left_shoulder: { id: 'left_shoulder', name: 'Left shoulder', position: [-25, -40], parent_id: 'root' }
          },
          root_joint_ids: ['root']
        }
      }
    });

    expect(project.parts.upper_arm_L.texturePath).toBe('parts/upper_arm_L.svg');
    expect(project.parts.upper_arm_L.anchorJoint).toBe('left_shoulder');
    expect(project.parts.upper_arm_L.transform.rotation).toBe(14);
    expect(project.skeleton?.joints.left_shoulder.parent).toBe('root');
    expect(project.skeleton?.bones).toContainEqual({ fromJoint: 'root', toJoint: 'left_shoulder' });
  });

  it('uses Result-style parsing for project import errors', () => {
    const result = parseProjectResult('{bad json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('invalid-json');
    }
  });
});

describe('resource and capability parity evidence', () => {
  it('maps every web mechanism family to a desktop resource or explicit web-only rationale', () => {
    const project = normalizeProject({});
    expect(project.resourceManifest.desktopResources).toEqual(expect.arrayContaining([
      'resources/mechanism_content/four_bar.json',
      'resources/mechanism_content/linkage_five_bar.json',
      'resources/mechanism_content/linkage_six_bar.json',
      'resources/mechanism_content/cam_follower.json',
      'resources/mechanism_content/gear_train.json',
      'resources/mechanism_content/slider_crank.json'
    ]));
    expect(resourceManifestEntries.every((entry) => entry.rationale.length > 12)).toBe(true);
    expect(mechanismResourceStatus('scotch-yoke')?.status).toBe('web-only');
  });

  it('fails feature audit when declared capabilities are not evidence-backed', () => {
    const project = normalizeProject({});
    const audit = buildFeatureAudit(project, {
      ...defaultFeatureAuditCapabilities,
      pwaManifest: false,
      serviceWorker: false,
      directHandles: false,
      physicsAwareness: false,
      resourceManifest: false,
      evidenceDriven: false
    });

    expect(audit.complete).toBe(false);
    expect(audit.missingRequired.map((item) => item.id)).toEqual(expect.arrayContaining([
      'direct-handles',
      'physics-aware-simulation',
      'foundry-lab-options',
      'web-shell'
    ]));
  });
});
