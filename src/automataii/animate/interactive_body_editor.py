# Interactive Body Parts Editor
# Lines: ~800
# Public API: InteractiveBodyEditor, run_interactive_editing
# Deps In (Afferent): 2 [CLI, body_parts_extractor]
# Deps Out (Efferent): 4 [cv2, numpy, matplotlib, json]
# Coupling: Medium (GUI interaction, image processing, skeletal data)
# Cohesion: Feature (interactive editing of body part boundaries)
# Owner: Alan Synn, Reviewers: Team
# Last Updated: 2025-01-15

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, RadioButtons

from .part_definitions import BODY_PARTS


class InteractiveBodyEditor:
    """Interactive editor for precise body part boundary definition"""

    def __init__(self, image_path: str, skeleton_data: dict[str, Any]):
        self.image_path = Path(image_path)
        self.skeleton_data = skeleton_data
        self.current_part = "torso"
        self.boundary_points = {}  # part_name -> list of boundary points
        self.joint_positions = {}
        self.selected_joints = set()  # Currently selected joints for boundary

        # Load and process image
        self.original_image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if self.original_image is None:
            raise ValueError(f"Could not load image: {image_path}")

        self.height, self.width = self.original_image.shape[:2]

        # Convert to RGB for matplotlib
        if len(self.original_image.shape) == 3:
            self.display_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        else:
            self.display_image = self.original_image

        # Extract joint positions from skeleton data
        self._extract_joint_positions()

        # Initialize boundary points for all parts
        for part_name in BODY_PARTS.keys():
            self.boundary_points[part_name] = []

        # Setup matplotlib figure
        self.fig, self.ax = plt.subplots(1, 1, figsize=(12, 16))
        self.fig.suptitle('Interactive Body Parts Editor', fontsize=16)

        # Display image
        self.ax.imshow(self.display_image)
        self.ax.set_xlim(0, self.width)
        self.ax.set_ylim(self.height, 0)  # Invert y-axis
        self.ax.set_aspect('equal')

        # Setup UI
        self._setup_ui()
        self._draw_skeleton()
        self._setup_event_handlers()

        print("Interactive Body Editor loaded!")
        print("Instructions:")
        print("1. Select a body part from the radio buttons")
        print("2. Click on the image to define boundary points for that part")
        print("3. Click on joints to include/exclude them from the part")
        print("4. Use 'Preview Segmentation' to see current boundaries")
        print("5. Use 'Save Boundaries' to save your work")
        print("6. Use 'Apply Segmentation' when satisfied with boundaries")

    def _extract_joint_positions(self):
        """Extract joint positions from skeleton data"""
        if 'joints' in self.skeleton_data:
            joints = self.skeleton_data['joints']
            if isinstance(joints, dict):
                for joint_id, joint_data in joints.items():
                    if isinstance(joint_data, dict) and 'position' in joint_data:
                        pos = joint_data['position']
                        if len(pos) >= 2:
                            # Extract joint name (remove _0, _1 suffixes)
                            joint_name = '_'.join(joint_id.split('_')[:-1])
                            if not joint_name:
                                joint_name = joint_id.split('_')[0]
                            self.joint_positions[joint_name] = (float(pos[0]), float(pos[1]))

        elif 'skeleton' in self.skeleton_data:
            skeleton = self.skeleton_data['skeleton']
            if isinstance(skeleton, list):
                for joint_data in skeleton:
                    if isinstance(joint_data, dict):
                        name = joint_data.get('name', '')
                        loc = joint_data.get('loc', [0, 0])
                        if name and len(loc) >= 2:
                            self.joint_positions[name] = (float(loc[0]), float(loc[1]))

        print(f"Extracted {len(self.joint_positions)} joint positions")

    def _setup_ui(self):
        """Setup UI controls"""
        # Create space for controls on the right
        self.ax.set_position([0.1, 0.1, 0.6, 0.8])

        # Part selection radio buttons
        parts_list = list(BODY_PARTS.keys())
        rax_parts = plt.axes([0.72, 0.6, 0.15, 0.3])
        self.radio_parts = RadioButtons(rax_parts, parts_list)
        self.radio_parts.on_clicked(self._on_part_selected)

        # Control buttons
        ax_preview = plt.axes([0.72, 0.5, 0.15, 0.04])
        self.btn_preview = Button(ax_preview, 'Preview Segmentation')
        self.btn_preview.on_clicked(self._preview_segmentation)

        ax_save = plt.axes([0.72, 0.45, 0.15, 0.04])
        self.btn_save = Button(ax_save, 'Save Boundaries')
        self.btn_save.on_clicked(self._save_boundaries)

        ax_load = plt.axes([0.72, 0.4, 0.15, 0.04])
        self.btn_load = Button(ax_load, 'Load Boundaries')
        self.btn_load.on_clicked(self._load_boundaries)

        ax_clear = plt.axes([0.72, 0.35, 0.15, 0.04])
        self.btn_clear = Button(ax_clear, 'Clear Current Part')
        self.btn_clear.on_clicked(self._clear_current_part)

        ax_apply = plt.axes([0.72, 0.25, 0.15, 0.04])
        self.btn_apply = Button(ax_apply, 'Apply Segmentation')
        self.btn_apply.on_clicked(self._apply_segmentation)

        ax_exit = plt.axes([0.72, 0.2, 0.15, 0.04])
        self.btn_exit = Button(ax_exit, 'Exit')
        self.btn_exit.on_clicked(self._exit_editor)

        # Status text
        self.status_text = self.fig.text(0.72, 0.15, f'Current Part: {self.current_part}',
                                        fontsize=10, weight='bold')
        self.info_text = self.fig.text(0.72, 0.12, 'Click to add boundary points',
                                      fontsize=9)

    def _draw_skeleton(self):
        """Draw skeleton joints and connections"""
        # Draw joints
        for joint_name, (x, y) in self.joint_positions.items():
            color = 'red' if joint_name in self.selected_joints else 'blue'
            circle = patches.Circle((x, y), radius=5, color=color, alpha=0.7)
            self.ax.add_patch(circle)

            # Add joint label
            self.ax.text(x+8, y, joint_name, fontsize=8, color='white',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))

        # Draw connections between joints (basic skeleton)
        self._draw_skeleton_connections()

    def _draw_skeleton_connections(self):
        """Draw basic skeleton connections"""
        connections = [
            ('head_top', 'neck'),
            ('neck', 'torso'),
            ('torso', 'pelvis'),
            ('neck', 'left_shoulder'),
            ('neck', 'right_shoulder'),
            ('left_shoulder', 'left_elbow'),
            ('left_elbow', 'left_wrist'),
            ('right_shoulder', 'right_elbow'),
            ('right_elbow', 'right_wrist'),
            ('pelvis', 'left_hip'),
            ('pelvis', 'right_hip'),
            ('left_hip', 'left_knee'),
            ('left_knee', 'left_ankle'),
            ('right_hip', 'right_knee'),
            ('right_knee', 'right_ankle'),
        ]

        for joint1, joint2 in connections:
            if joint1 in self.joint_positions and joint2 in self.joint_positions:
                x1, y1 = self.joint_positions[joint1]
                x2, y2 = self.joint_positions[joint2]
                self.ax.plot([x1, x2], [y1, y2], 'g--', alpha=0.5, linewidth=2)

    def _setup_event_handlers(self):
        """Setup mouse and keyboard event handlers"""
        self.fig.canvas.mpl_connect('button_press_event', self._on_click)
        self.fig.canvas.mpl_connect('key_press_event', self._on_key_press)

    def _on_part_selected(self, label):
        """Handle part selection from radio buttons"""
        self.current_part = label
        self.status_text.set_text(f'Current Part: {self.current_part}')
        self.info_text.set_text(f'Boundary points: {len(self.boundary_points[self.current_part])}')
        self._update_display()

    def _on_click(self, event):
        """Handle mouse clicks on the image"""
        if event.inaxes != self.ax:
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        # Check if clicking near a joint
        clicked_joint = self._find_nearest_joint(x, y, threshold=20)

        if event.button == 1:  # Left click
            if clicked_joint:
                # Toggle joint selection
                if clicked_joint in self.selected_joints:
                    self.selected_joints.remove(clicked_joint)
                    print(f"Removed joint {clicked_joint} from {self.current_part}")
                else:
                    self.selected_joints.add(clicked_joint)
                    print(f"Added joint {clicked_joint} to {self.current_part}")
            else:
                # Add boundary point
                self.boundary_points[self.current_part].append((x, y))
                print(f"Added boundary point ({x:.1f}, {y:.1f}) to {self.current_part}")

        elif event.button == 3:  # Right click
            if clicked_joint and clicked_joint in self.selected_joints:
                self.selected_joints.remove(clicked_joint)
                print(f"Removed joint {clicked_joint}")
            elif self.boundary_points[self.current_part]:
                # Remove last boundary point
                removed_point = self.boundary_points[self.current_part].pop()
                print(f"Removed boundary point {removed_point} from {self.current_part}")

        self.info_text.set_text(f'Boundary points: {len(self.boundary_points[self.current_part])}, '
                               f'Selected joints: {len(self.selected_joints)}')
        self._update_display()

    def _find_nearest_joint(self, x: float, y: float, threshold: float = 20) -> str | None:
        """Find the nearest joint to the click position"""
        min_distance = float('inf')
        nearest_joint = None

        for joint_name, (jx, jy) in self.joint_positions.items():
            distance = np.sqrt((x - jx)**2 + (y - jy)**2)
            if distance < threshold and distance < min_distance:
                min_distance = distance
                nearest_joint = joint_name

        return nearest_joint

    def _on_key_press(self, event):
        """Handle keyboard shortcuts"""
        if event.key == 'c':
            self._clear_current_part(None)
        elif event.key == 'p':
            self._preview_segmentation(None)
        elif event.key == 's':
            self._save_boundaries(None)
        elif event.key == 'q':
            self._exit_editor(None)

    def _update_display(self):
        """Update the display with current boundary points and selections"""
        # Clear previous boundary points and joint highlights
        for artist in self.ax.patches[:]:
            if hasattr(artist, '_boundary_marker'):
                artist.remove()

        # Redraw joints with current selection state
        for joint_name, (x, y) in self.joint_positions.items():
            color = 'red' if joint_name in self.selected_joints else 'blue'
            circle = patches.Circle((x, y), radius=5, color=color, alpha=0.7)
            circle._boundary_marker = True
            self.ax.add_patch(circle)

        # Draw boundary points for current part
        if self.boundary_points[self.current_part]:
            points = np.array(self.boundary_points[self.current_part])
            self.ax.scatter(points[:, 0], points[:, 1], c='yellow', s=50, alpha=0.8,
                           marker='x', linewidths=2)

            # Connect boundary points with lines
            if len(points) > 1:
                for i in range(len(points)):
                    next_i = (i + 1) % len(points)
                    self.ax.plot([points[i, 0], points[next_i, 0]],
                               [points[i, 1], points[next_i, 1]],
                               'y-', alpha=0.6, linewidth=2)

        self.fig.canvas.draw()

    def _clear_current_part(self, event):
        """Clear boundary points for current part"""
        self.boundary_points[self.current_part] = []
        self.selected_joints.clear()
        self.info_text.set_text(f'Cleared {self.current_part}')
        self._update_display()

    def _preview_segmentation(self, event):
        """Preview segmentation with current boundary settings"""
        print("Generating segmentation preview...")

        try:
            # Create custom segmentation based on user-defined boundaries
            preview_image = self._generate_preview_segmentation()

            # Show preview in new window
            fig_preview, ax_preview = plt.subplots(1, 2, figsize=(16, 8))

            ax_preview[0].imshow(self.display_image)
            ax_preview[0].set_title('Original Image')
            ax_preview[0].axis('off')

            ax_preview[1].imshow(preview_image)
            ax_preview[1].set_title('Segmentation Preview')
            ax_preview[1].axis('off')

            plt.show()

        except Exception as e:
            print(f"Error generating preview: {e}")
            self.info_text.set_text(f'Preview error: {str(e)[:50]}...')

    def _generate_preview_segmentation(self) -> np.ndarray:
        """Generate sophisticated segmentation preview with joint-based and boundary-based regions"""
        # Create a colored segmentation mask
        preview = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Define colors for each part
        colors = {
            'head': (255, 100, 100),
            'torso': (100, 255, 100),
            'left_arm_upper': (100, 100, 255),
            'right_arm_upper': (255, 255, 100),
            'left_arm_lower': (255, 100, 255),
            'right_arm_lower': (100, 255, 255),
            'left_leg_upper': (200, 100, 50),
            'right_leg_upper': (50, 200, 100),
            'left_leg_lower': (100, 50, 200),
            'right_leg_lower': (200, 200, 50),
        }

        # Process each part
        for part_name, part_def in BODY_PARTS.items():
            mask = self._create_part_preview_mask(part_name, part_def)
            if np.sum(mask) > 0:
                color = colors.get(part_name, (128, 128, 128))
                preview[mask > 0] = color

        # Blend with original image
        alpha = 0.6
        if len(self.original_image.shape) == 3:
            original_rgb = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        else:
            original_rgb = cv2.cvtColor(self.original_image, cv2.COLOR_GRAY2RGB)

        blended = cv2.addWeighted(original_rgb, 1-alpha, preview, alpha, 0)

        return blended

    def _create_part_preview_mask(self, part_name: str, part_def: dict) -> np.ndarray:
        """Create preview mask for a single part combining user boundaries and joint information"""
        mask = np.zeros((self.height, self.width), dtype=np.uint8)

        # Method 1: User-defined boundary polygon
        if len(self.boundary_points[part_name]) >= 3:
            points = np.array(self.boundary_points[part_name], dtype=np.int32)
            cv2.fillPoly(mask, [points], 255)
            return mask

        # Method 2: Joint-based automatic generation (fallback)
        joints = part_def.get('joints', [])
        part_joints = []

        for joint in joints:
            if joint in self.joint_positions:
                part_joints.append(self.joint_positions[joint])
            else:
                # Try to find joint by partial name matching
                for jname, pos in self.joint_positions.items():
                    if jname.startswith(joint) or joint in jname:
                        part_joints.append(pos)
                        break

        if len(part_joints) >= 2:
            # Create convex hull around joints
            hull_points = cv2.convexHull(np.array(part_joints, dtype=np.int32))

            # Expand hull slightly for better coverage
            center = np.mean(hull_points.squeeze(), axis=0)
            expanded_points = []
            for point in hull_points.squeeze():
                direction = point - center
                expanded_point = center + direction * 1.3  # 30% expansion
                expanded_points.append(expanded_point.astype(np.int32))

            cv2.fillPoly(mask, [np.array(expanded_points)], 255)

        return mask

    def _save_boundaries(self, event):
        """Save current boundary definitions to file"""
        save_path = self.image_path.parent / "boundary_definitions.json"

        # Prepare data for saving
        save_data = {
            'image_path': str(self.image_path),
            'boundary_points': {k: [[float(x), float(y)] for x, y in v]
                               for k, v in self.boundary_points.items()},
            'joint_positions': {k: [float(x), float(y)] for k, (x, y) in self.joint_positions.items()},
            'skeleton_data': self.skeleton_data
        }

        try:
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=4)
            print(f"Boundaries saved to: {save_path}")
            self.info_text.set_text(f'Saved to {save_path.name}')
        except Exception as e:
            print(f"Error saving boundaries: {e}")
            self.info_text.set_text(f'Save error: {str(e)[:30]}...')

    def _load_boundaries(self, event):
        """Load boundary definitions from file"""
        load_path = self.image_path.parent / "boundary_definitions.json"

        if not load_path.exists():
            print(f"No boundary file found at: {load_path}")
            self.info_text.set_text('No boundary file found')
            return

        try:
            with open(load_path) as f:
                load_data = json.load(f)

            # Load boundary points
            for part_name, points_list in load_data.get('boundary_points', {}).items():
                self.boundary_points[part_name] = [(x, y) for x, y in points_list]

            print(f"Boundaries loaded from: {load_path}")
            self.info_text.set_text(f'Loaded from {load_path.name}')
            self._update_display()

        except Exception as e:
            print(f"Error loading boundaries: {e}")
            self.info_text.set_text(f'Load error: {str(e)[:30]}...')

    def _apply_segmentation(self, event):
        """Apply the final segmentation and save results"""
        print("Applying final segmentation with user-defined boundaries...")

        try:
            # Generate final segmentation
            final_masks = self._generate_final_segmentation()

            # Save individual part masks
            output_dir = self.image_path.parent / "interactive_output"
            output_dir.mkdir(exist_ok=True)

            for part_name, mask in final_masks.items():
                mask_path = output_dir / f"{part_name}_mask.png"
                cv2.imwrite(str(mask_path), mask)

            # Generate visualization
            viz_image = self._generate_final_visualization(final_masks)
            viz_path = output_dir / "interactive_segmentation_result.png"
            cv2.imwrite(str(viz_path), viz_image)

            print(f"Interactive segmentation completed! Results saved to: {output_dir}")
            self.info_text.set_text('Segmentation applied successfully!')

        except Exception as e:
            print(f"Error applying segmentation: {e}")
            self.info_text.set_text(f'Apply error: {str(e)[:30]}...')

    def _generate_final_segmentation(self) -> dict[str, np.ndarray]:
        """Generate final segmentation masks based on user boundaries"""
        masks = {}

        for part_name, boundary_points in self.boundary_points.items():
            if len(boundary_points) >= 3:
                # Create mask from user-defined polygon
                points = np.array(boundary_points, dtype=np.int32)
                mask = np.zeros((self.height, self.width), dtype=np.uint8)
                cv2.fillPoly(mask, [points], 255)
                masks[part_name] = mask
            else:
                # Empty mask if no boundaries defined
                masks[part_name] = np.zeros((self.height, self.width), dtype=np.uint8)

        return masks

    def _generate_final_visualization(self, masks: dict[str, np.ndarray]) -> np.ndarray:
        """Generate final visualization image"""
        # Create overlay with different colors for each part
        overlay = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
            (0, 255, 255), (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0)
        ]

        for i, (part_name, mask) in enumerate(masks.items()):
            if np.sum(mask) > 0:
                color = colors[i % len(colors)]
                overlay[mask > 0] = color

        # Blend with original image
        if len(self.original_image.shape) == 3:
            base_image = self.original_image.copy()
        else:
            base_image = cv2.cvtColor(self.original_image, cv2.COLOR_GRAY2BGR)

        result = cv2.addWeighted(base_image, 0.7, overlay, 0.3, 0)
        return result

    def _exit_editor(self, event):
        """Exit the interactive editor"""
        print("Exiting interactive body editor...")
        plt.close('all')

    def run(self):
        """Start the interactive editing session"""
        plt.show()


def run_interactive_editing(image_path: str, skeleton_path: str = None):
    """Run interactive body parts editing mode"""

    print(f"Starting interactive editing for: {image_path}")

    # Load skeleton data
    if skeleton_path:
        skeleton_file = Path(skeleton_path)
    else:
        # Look for skeleton data in same directory
        image_file = Path(image_path)
        skeleton_file = image_file.parent / "char_cfg.yaml"

        if not skeleton_file.exists():
            skeleton_file = image_file.parent / "skeleton.json"

    if skeleton_file.exists():
        import yaml
        if skeleton_file.suffix.lower() in ['.yaml', '.yml']:
            with open(skeleton_file) as f:
                skeleton_data = yaml.safe_load(f)
        else:
            with open(skeleton_file) as f:
                skeleton_data = json.load(f)
    else:
        print("Warning: No skeleton data found. Using default joint positions.")
        # Create default skeleton based on image dimensions
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        height, width = img.shape[:2]
        skeleton_data = create_default_skeleton(width, height)

    # Create and run editor
    editor = InteractiveBodyEditor(image_path, skeleton_data)
    editor.run()


def create_default_skeleton(width: int, height: int) -> dict[str, Any]:
    """Create default skeleton joint positions based on image dimensions"""
    return {
        'joints': {
            'head_top_0': {'position': [width // 2, int(height * 0.05)]},
            'neck_0': {'position': [width // 2, int(height * 0.12)]},
            'torso_0': {'position': [width // 2, int(height * 0.25)]},
            'pelvis_0': {'position': [width // 2, int(height * 0.45)]},
            'left_shoulder_0': {'position': [int(width * 0.35), int(height * 0.18)]},
            'right_shoulder_0': {'position': [int(width * 0.65), int(height * 0.18)]},
            'left_elbow_0': {'position': [int(width * 0.20), int(height * 0.30)]},
            'right_elbow_0': {'position': [int(width * 0.80), int(height * 0.30)]},
            'left_wrist_0': {'position': [int(width * 0.15), int(height * 0.42)]},
            'right_wrist_0': {'position': [int(width * 0.85), int(height * 0.42)]},
            'left_hip_0': {'position': [int(width * 0.42), int(height * 0.45)]},
            'right_hip_0': {'position': [int(width * 0.58), int(height * 0.45)]},
            'left_knee_0': {'position': [int(width * 0.40), int(height * 0.65)]},
            'right_knee_0': {'position': [int(width * 0.60), int(height * 0.65)]},
            'left_ankle_0': {'position': [int(width * 0.38), int(height * 0.85)]},
            'right_ankle_0': {'position': [int(width * 0.62), int(height * 0.85)]},
        }
    }


def main():
    """CLI entry point for interactive editing mode"""
    parser = argparse.ArgumentParser(description='Interactive Body Parts Editor')
    parser.add_argument('image', help='Path to the character image')
    parser.add_argument('--skeleton', help='Path to skeleton data (optional)')
    parser.add_argument('--editing', action='store_true', help='Enable interactive editing mode')

    args = parser.parse_args()

    if args.editing:
        run_interactive_editing(args.image, args.skeleton)
    else:
        print("Use --editing flag to start interactive editing mode")
        print("Example: python -m automataii.animate.interactive_body_editor image.png --editing")


if __name__ == "__main__":
    main()
