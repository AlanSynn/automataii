#!/usr/bin/env python

from typing import Optional, Dict, Any, List, Tuple
import cv2
import numpy as np
import yaml
import os
from pathlib import Path
import json
import argparse
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_fill_holes
from scipy.spatial.distance import cdist
import networkx as nx
from collections import defaultdict
import random
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from automataii.animate.body_parts_animation import animate_body_part, save_animation
from automataii.animate.part_definitions import BODY_PARTS
from automataii.animate.templates import HTML_VIEWER_TEMPLATE, PART_CARD_TEMPLATE
from automataii.utils.image_utils import save_image


class FastSkeletonSegmenter:
    """Optimized skeleton-driven body part segmentation"""

    def __init__(
        self,
        mask: np.ndarray,
        joint_map: Dict[str, Tuple[int, int]],
        part_definitions: Dict[str, Any],
        scale_factor: float = 0.5,
    ):
        self.mask = mask
        self.joint_map = joint_map
        self.part_definitions = part_definitions
        self.height, self.width = mask.shape
        self.scale_factor = scale_factor

        # Pre-compute scaled versions for faster processing
        self.scaled_height = int(self.height * scale_factor)
        self.scaled_width = int(self.width * scale_factor)
        self.scaled_mask = cv2.resize(
            mask,
            (self.scaled_width, self.scaled_height),
            interpolation=cv2.INTER_NEAREST,
        )

        # Pre-compute coordinate grids
        self.y_grid, self.x_grid = np.mgrid[
            0 : self.scaled_height, 0 : self.scaled_width
        ]
        self.coords = np.column_stack([self.x_grid.ravel(), self.y_grid.ravel()])

        # Cache for distance computations
        self._distance_cache = {}

    def segment_fast(self) -> Dict[str, np.ndarray]:
        """Fast segmentation using vectorized operations"""
        # Create part influence maps
        influence_maps = self._create_all_influence_maps()

        if not influence_maps:
            return {}

        # Stack all influence maps
        influence_stack = np.stack(list(influence_maps.values()), axis=0)

        # Find maximum influence per pixel (vectorized)
        max_indices = np.argmax(influence_stack, axis=0)

        # Create masks
        part_masks = {}
        part_names = list(influence_maps.keys())

        for idx, part_name in enumerate(part_names):
            # Create binary mask at scaled resolution
            scaled_mask = (max_indices == idx).astype(np.uint8) * 255
            scaled_mask = cv2.bitwise_and(scaled_mask, self.scaled_mask)

            # Upscale to original resolution
            full_mask = cv2.resize(
                scaled_mask, (self.width, self.height), interpolation=cv2.INTER_NEAREST
            )

            # Clean up
            full_mask = self._fast_postprocess(full_mask)
            full_mask = cv2.bitwise_and(full_mask, self.mask)

            part_masks[part_name] = full_mask

        return part_masks

    def _create_all_influence_maps(self) -> Dict[str, np.ndarray]:
        """Create all influence maps using parallel processing"""
        influence_maps = {}

        # Process parts in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for part_name, part_def in self.part_definitions.items():
                future = executor.submit(
                    self._create_part_influence_vectorized, part_name, part_def
                )
                futures[part_name] = future

            for part_name, future in futures.items():
                influence = future.result()
                if influence is not None:
                    influence_maps[part_name] = influence

        return influence_maps

    def _create_part_influence_vectorized(
        self, part_name: str, part_def: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Create influence map using vectorized operations"""
        joints = part_def.get("joints", [])
        if not joints:
            return None

        # Map joints to actual names
        mapped_joints = []
        for joint in joints:
            if joint in self.joint_map:
                mapped_joints.append(joint)
            else:
                for jname in self.joint_map:
                    if jname.startswith(joint):
                        mapped_joints.append(jname)
                        break

        if not mapped_joints:
            return None

        # Scale joint positions
        scaled_joints = []
        for joint in mapped_joints:
            x, y = self.joint_map[joint]
            scaled_joints.append(
                (int(x * self.scale_factor), int(y * self.scale_factor))
            )

        # Create influence map
        influence = np.zeros((self.scaled_height, self.scaled_width), dtype=np.float32)

        # Bone influences (vectorized)
        for i in range(len(scaled_joints) - 1):
            bone_influence = self._create_bone_influence_vectorized(
                scaled_joints[i], scaled_joints[i + 1]
            )
            influence = np.maximum(influence, bone_influence)

        # Joint influences (vectorized)
        joint_positions = np.array(scaled_joints)
        if joint_positions.shape[0] > 0:
            # Compute distances from all pixels to all joints at once
            distances = cdist(self.coords, joint_positions, metric="euclidean")

            # Gaussian influence for each joint
            sigma = 30 * self.scale_factor
            joint_influences = np.exp(-(distances**2) / (2 * sigma**2))

            # Take maximum influence across all joints
            max_joint_influence = np.max(joint_influences, axis=1)
            max_joint_influence = max_joint_influence.reshape(
                self.scaled_height, self.scaled_width
            )
            influence = np.maximum(influence, max_joint_influence)

        # Apply part-specific modulation
        influence = self._apply_part_modulation_fast(influence, part_name)

        return influence

    def _create_bone_influence_vectorized(
        self, p1: Tuple[int, int], p2: Tuple[int, int]
    ) -> np.ndarray:
        """Vectorized bone influence calculation"""
        # Cache key
        cache_key = (p1, p2)
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        # Line parameters
        p1 = np.array(p1, dtype=np.float32)
        p2 = np.array(p2, dtype=np.float32)
        line_vec = p2 - p1
        line_length = np.linalg.norm(line_vec)

        if line_length == 0:
            return np.zeros((self.scaled_height, self.scaled_width), dtype=np.float32)

        line_vec_norm = line_vec / line_length

        # Vectorized distance to line segment
        # Vector from p1 to each pixel
        pixel_vecs = self.coords - p1

        # Project onto line
        projections = np.dot(pixel_vecs, line_vec_norm)
        projections = np.clip(projections, 0, line_length)

        # Closest points on line
        closest_points = p1 + projections[:, np.newaxis] * line_vec_norm

        # Distances
        distances = np.linalg.norm(self.coords - closest_points, axis=1)
        distances = distances.reshape(self.scaled_height, self.scaled_width)

        # Convert to influence
        sigma = (20 + line_length * 0.1) * self.scale_factor
        influence = np.exp(-(distances**2) / (2 * sigma**2))

        # Cache result
        self._distance_cache[cache_key] = influence

        return influence

    def _apply_part_modulation_fast(
        self, influence: np.ndarray, part_name: str
    ) -> np.ndarray:
        """Fast part-specific modulation"""
        if "head" in part_name:
            # Boost upper region
            y_gradient = np.linspace(1, 0, self.scaled_height)[:, np.newaxis]
            influence *= 1 + 0.5 * y_gradient

        elif "torso" in part_name:
            # Slight blur and boost
            influence = gaussian_filter(influence, sigma=2)
            influence *= 1.2

        elif any(term in part_name for term in ["arm", "leg"]):
            # Light blur
            influence = gaussian_filter(influence, sigma=1)

        return influence

    def _fast_postprocess(self, mask: np.ndarray) -> np.ndarray:
        """Fast post-processing"""
        # Simple morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Fast median filter
        mask = cv2.medianBlur(mask, 3)

        return mask


class BodyPartsExtractor:
    def __init__(
        self,
        char_dir: str,
        output_dir: Optional[str] = None,
        generate_animations: bool = False,
        num_frames: int = 30,
        fps: int = 24,
    ):
        self.char_dir = Path(char_dir)
        self.output_dir = Path(output_dir)
        self.generate_animations = generate_animations
        self.num_frames = num_frames
        self.fps = fps

        self.char_cfg: Optional[Dict[str, Any]] = None
        self.texture: Optional[np.ndarray] = None
        self.mask: Optional[np.ndarray] = None
        self.texture_relative_joint_map: Optional[Dict[str, Tuple[int, int]]] = None
        self.part_masks: Optional[Dict[str, np.ndarray]] = None
        self.results: Optional[Dict[str, Any]] = None
        self.image_height: Optional[int] = None
        self.image_width: Optional[int] = None

    def _read_char_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except:
            return None

    def _create_joint_map(self, skeleton_data: Any) -> Dict[str, Tuple[int, int]]:
        joint_map = {}

        # Handle different skeleton data formats
        if isinstance(skeleton_data, dict):
            # New format with 'joints' key
            if "joints" in skeleton_data:
                joints = skeleton_data["joints"]
                if isinstance(joints, dict):
                    # joints is a dict of joint_id -> joint_data
                    for joint_id, joint_data in joints.items():
                        if isinstance(joint_data, dict) and "position" in joint_data:
                            pos = joint_data["position"]
                            if len(pos) >= 2:
                                # Extract joint name from id
                                joint_name = "_".join(joint_id.split("_")[:-1])
                                if not joint_name:
                                    joint_name = joint_id.split("_")[0]
                                joint_map[joint_name] = (int(pos[0]), int(pos[1]))
                elif isinstance(joints, list):
                    # joints is a list
                    for joint in joints:
                        if "name" in joint and "position" in joint:
                            joint_map[joint["name"]] = tuple(joint["position"])
            # Also check 'joint_map' key
            elif "joint_map" in skeleton_data:
                joint_map_data = skeleton_data["joint_map"]
                if isinstance(joint_map_data, dict):
                    for joint_name, pos in joint_map_data.items():
                        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                            joint_map[joint_name] = (int(pos[0]), int(pos[1]))
        elif isinstance(skeleton_data, list):
            # Old format - list of joints
            for joint in skeleton_data:
                if "name" in joint and "loc" in joint:
                    joint_map[joint["name"]] = tuple(joint["loc"])

        return joint_map

    def _get_proximal_joint_name(
        self, part_name: str, part_definition: Dict[str, Any]
    ) -> Optional[str]:
        if part_name == "head":
            return "neck"
        if part_name == "torso":
            return None
        joints = part_definition.get("joints")
        if joints and isinstance(joints, list) and len(joints) > 0:
            return joints[0]
        return None

    def _load_initial_data(self) -> bool:
        char_cfg_path = os.path.join(self.char_dir, "char_cfg.yaml")
        texture_path = os.path.join(self.char_dir, "texture.png")
        mask_path = os.path.join(self.char_dir, "mask.png")

        if not all(os.path.exists(p) for p in [char_cfg_path, texture_path, mask_path]):
            return False

        self.char_cfg = self._read_char_config(char_cfg_path)
        self.texture = cv2.imread(texture_path, cv2.IMREAD_UNCHANGED)
        self.mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        if self.char_cfg is None or self.texture is None or self.mask is None:
            return False

        self.image_height = self.char_cfg["height"]
        self.image_width = self.char_cfg["width"]
        return True

    def _prepare_joint_map(self):
        if not self.char_cfg:
            return

        # Try different possible keys for skeleton data
        skeleton_data = None
        if "skeleton" in self.char_cfg:
            skeleton_data = self.char_cfg["skeleton"]
        elif "joints" in self.char_cfg:
            # If char_cfg directly contains joints
            skeleton_data = self.char_cfg

        if skeleton_data:
            self.texture_relative_joint_map = self._create_joint_map(skeleton_data)

    def _segment_body_parts(self) -> Dict[str, np.ndarray]:
        """Fast body part segmentation"""
        if self.mask is None or self.texture_relative_joint_map is None:
            return {}

        # Determine scale factor based on image size
        max_dim = max(self.mask.shape)
        if max_dim > 1024:
            scale_factor = 512.0 / max_dim
        elif max_dim > 512:
            scale_factor = 0.7
        else:
            scale_factor = 1.0

        # Use fast segmenter
        segmenter = FastSkeletonSegmenter(
            self.mask,
            self.texture_relative_joint_map,
            BODY_PARTS,
            scale_factor=scale_factor,
        )

        # Perform fast segmentation
        part_masks = segmenter.segment_fast()

        # Ensure all expected parts have masks
        for part_name in BODY_PARTS:
            if part_name not in part_masks:
                part_masks[part_name] = np.zeros_like(self.mask)

        return part_masks

    def _visualize_segmentation(self):
        if (
            self.mask is None
            or not self.part_masks
            or self.texture_relative_joint_map is None
        ):
            return

        output_path = os.path.join(self.output_dir, "segmentation_vis.png")
        height, width = self.mask.shape
        vis_image = np.zeros((height, width, 3), dtype=np.uint8)

        colors = {
            "head": (255, 0, 0),
            "torso": (0, 255, 0),
            "left_arm_upper": (0, 0, 255),
            "left_arm_lower": (255, 255, 0),
            "right_arm_upper": (255, 0, 255),
            "right_arm_lower": (0, 255, 255),
            "left_leg_upper": (128, 0, 0),
            "left_leg_lower": (0, 128, 0),
            "right_leg_upper": (0, 0, 128),
            "right_leg_lower": (128, 128, 0),
        }

        for part_name, part_mask in self.part_masks.items():
            if part_name in colors:
                color = colors[part_name]
                colored_mask = np.zeros((height, width, 3), dtype=np.uint8)
                colored_mask[part_mask > 0] = color
                vis_image = cv2.addWeighted(vis_image, 1.0, colored_mask, 0.5, 0)

        for joint_name, joint_pos in self.texture_relative_joint_map.items():
            cv2.circle(vis_image, joint_pos, 5, (255, 255, 255), -1)
            cv2.putText(
                vis_image,
                joint_name,
                (joint_pos[0] + 5, joint_pos[1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        cv2.imwrite(output_path, vis_image)

    def _extract_body_part(
        self, full_texture: np.ndarray, part_mask_data: np.ndarray
    ) -> Tuple[
        Optional[np.ndarray], Optional[np.ndarray], Optional[Tuple[int, int, int, int]]
    ]:
        if part_mask_data is None or np.sum(part_mask_data) == 0:
            return None, None, None

        if part_mask_data.dtype != np.uint8:
            part_mask_data = part_mask_data.astype(np.uint8)

        # Use cv2.findNonZero for faster bounding box
        points = cv2.findNonZero(part_mask_data)
        if points is None:
            return None, None, None

        x, y, w, h = cv2.boundingRect(points)

        # Add padding
        padding = 3
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(full_texture.shape[1] - x, w + 2 * padding)
        h = min(full_texture.shape[0] - y, h + 2 * padding)

        if w == 0 or h == 0:
            return None, None, None

        part_texture_cropped = full_texture[y : y + h, x : x + w]
        alpha_channel_cropped = part_mask_data[y : y + h, x : x + w]
        alpha_channel_cropped = np.where(alpha_channel_cropped > 0, 255, 0).astype(
            np.uint8
        )

        return part_texture_cropped, alpha_channel_cropped, (x, y, w, h)

    def _generate_html_viewer(self):
        if (
            not self.results
            or "character" not in self.results
            or "parts" not in self.results["character"]
        ):
            return

        part_cards = ""
        for part_name, part_info in self.results["character"]["parts"].items():
            image_path = os.path.basename(part_info.get("image_path", ""))
            svg_path = os.path.basename(part_info.get("svg_path", ""))
            animation_element = ""
            if (
                "animations" in self.results["character"]
                and part_name in self.results["character"]["animations"]
            ):
                animation_path = os.path.basename(
                    self.results["character"]["animations"][part_name]["animation_path"]
                )
                animation_element = f'<div class="animation-container"><h4>Animation</h4><img src="{animation_path}" alt="{part_name} Animation" class="part-animation"></div>'
            part_card = PART_CARD_TEMPLATE.format(
                part_name=part_name.replace("_", " ").title(),
                image_path=image_path,
                svg_path=svg_path,
                animation_element=animation_element,
            )
            part_cards += part_card

        texture_path = os.path.relpath(
            os.path.join(self.char_dir, "image.png"), self.output_dir
        )
        segmentation_path = "segmentation_vis.png"
        html_content = HTML_VIEWER_TEMPLATE.format(
            texture_path=texture_path,
            segmentation_path=segmentation_path,
            part_cards=part_cards,
        )
        html_output_path = os.path.join(self.output_dir, "viewer.html")
        with open(html_output_path, "w") as f:
            f.write(html_content)

    def process(self):
        if not self._load_initial_data():
            return

        self._prepare_joint_map()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Time the segmentation
        import time

        start_time = time.time()
        self.part_masks = self._segment_body_parts()
        print(f"Segmentation took {time.time() - start_time:.2f} seconds")

        if not self.part_masks:
            return

        self._visualize_segmentation()

        self.results = {
            "character": {
                "width": int(self.image_width) if self.image_width else 0,
                "height": int(self.image_height) if self.image_height else 0,
                "parts": {},
                "joint_map": (
                    self.texture_relative_joint_map
                    if self.texture_relative_joint_map
                    else {}
                ),
                "skeleton": (
                    self.char_cfg.get("skeleton", self.char_cfg.get("joints", []))
                    if self.char_cfg
                    else []
                ),
                "animations": {},
            }
        }

        for part_name, part_mask_data in self.part_masks.items():
            part_image_texture, alpha_channel, part_bbox_coords = (
                self._extract_body_part(self.texture, part_mask_data)
            )

            if part_image_texture is None or part_bbox_coords is None:
                continue

            roi_x, roi_y, roi_w, roi_h = part_bbox_coords

            # Save PNG
            png_file_path = self.output_dir / f"{part_name}.png"

            # Create BGRA image
            if part_image_texture.ndim == 2:
                bgr_texture = cv2.cvtColor(part_image_texture, cv2.COLOR_GRAY2BGR)
                bgra_image = cv2.cvtColor(bgr_texture, cv2.COLOR_BGR2BGRA)
            elif part_image_texture.shape[2] == 3:
                bgra_image = cv2.cvtColor(part_image_texture, cv2.COLOR_BGR2BGRA)
            else:
                bgra_image = part_image_texture

            if bgra_image.shape[2] == 4 and alpha_channel is not None:
                bgra_image[:, :, 3] = alpha_channel

            cv2.imwrite(str(png_file_path), bgra_image)

            # Calculate pivot
            current_part_def = BODY_PARTS.get(part_name, {})
            anchor_joint_id = current_part_def.get("anchor_joint")

            local_pivot_x = float(roi_w / 2)
            local_pivot_y = float(roi_h / 2)

            if anchor_joint_id and self.texture_relative_joint_map:
                # Try exact match first
                anchor_joint_found = anchor_joint_id
                if anchor_joint_id not in self.texture_relative_joint_map:
                    # Try to find by prefix
                    anchor_joint_found = None
                    for jname in self.texture_relative_joint_map:
                        if jname.startswith(anchor_joint_id):
                            anchor_joint_found = jname
                            break

                if (
                    anchor_joint_found
                    and anchor_joint_found in self.texture_relative_joint_map
                ):
                    anchor_tex_x, anchor_tex_y = self.texture_relative_joint_map[
                        anchor_joint_found
                    ]
                    local_pivot_x = float(anchor_tex_x - roi_x)
                    local_pivot_y = float(anchor_tex_y - roi_y)

            self.results["character"]["parts"][part_name] = {
                "name": part_name,
                "roi": [float(roi_x), float(roi_y), float(roi_w), float(roi_h)],
                "image_path": str(png_file_path),
                "fill_color": current_part_def.get(
                    "color",
                    f"rgba({random.randint(0, 255)},{random.randint(0, 255)},{random.randint(0, 255)},0.5)",
                ),
                "local_pivot_offset": [local_pivot_x, local_pivot_y],
                "z_value": float(current_part_def.get("z_value", 0.0)),
                "fixed": bool(current_part_def.get("fixed", False)),
                "anchor_joint_id": anchor_joint_id,
            }

            if self.generate_animations:
                proximal_joint_name = self._get_proximal_joint_name(
                    part_name, current_part_def
                )
                if proximal_joint_name and self.texture_relative_joint_map:
                    # Try exact match first
                    proximal_joint_found = proximal_joint_name
                    if proximal_joint_name not in self.texture_relative_joint_map:
                        # Try to find by prefix
                        proximal_joint_found = None
                        for jname in self.texture_relative_joint_map:
                            if jname.startswith(proximal_joint_name):
                                proximal_joint_found = jname
                                break

                    if (
                        proximal_joint_found
                        and proximal_joint_found in self.texture_relative_joint_map
                    ):
                        pivot_point = self.texture_relative_joint_map[
                            proximal_joint_found
                        ]
                        local_pivot_for_anim = (
                            pivot_point[0] - roi_x,
                            pivot_point[1] - roi_y,
                        )

                        animation_frames = animate_body_part(
                            part_image_texture,
                            local_pivot_for_anim,
                            num_frames=self.num_frames,
                        )
                        animation_output_path = (
                            self.output_dir / f"{part_name}_animation.gif"
                        )
                        save_animation(
                            animation_frames, str(animation_output_path), fps=self.fps
                        )
                        self.results["character"]["animations"][part_name] = {
                            "animation_path": str(animation_output_path),
                        }

        self._generate_html_viewer()

        # Save parts info
        pydantic_skeleton_joints = []

        # Get skeleton data with fallbacks
        skeleton_data = self.char_cfg.get("skeleton", []) if self.char_cfg else []
        if not skeleton_data and self.char_cfg and "joints" in self.char_cfg:
            # Try to construct from joints data
            joints_data = self.char_cfg["joints"]
            if isinstance(joints_data, dict):
                for joint_id, joint_info in joints_data.items():
                    if isinstance(joint_info, dict):
                        # Extract joint name from id
                        joint_name = "_".join(joint_id.split("_")[:-1])
                        if not joint_name:
                            joint_name = joint_id.split("_")[0]

                        pos = joint_info.get("position", [0.0, 0.0])
                        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                            pos = [float(pos[0]), float(pos[1])]
                        else:
                            pos = [0.0, 0.0]

                        parent = joint_info.get("parent")

                        pydantic_skeleton_joints.append(
                            {
                                "id": joint_name,
                                "name": joint_name,
                                "position": pos,
                                "parent": parent,
                            }
                        )
        elif isinstance(skeleton_data, list):
            # Old format
            raw_joint_map = {
                j_data.get("name"): j_data
                for j_data in skeleton_data
                if isinstance(j_data, dict)
            }

            for joint_data in skeleton_data:
                if not isinstance(joint_data, dict):
                    continue

                joint_name = joint_data.get("name")
                if not joint_name:
                    continue

                loc = joint_data.get("loc", [0.0, 0.0])
                if not (isinstance(loc, list) and len(loc) == 2):
                    loc = [0.0, 0.0]

                parent_name = joint_data.get("parent")

                pydantic_skeleton_joints.append(
                    {
                        "id": joint_name,
                        "name": joint_name,
                        "position": [float(loc[0]), float(loc[1])],
                        "parent": parent_name if parent_name in raw_joint_map else None,
                    }
                )

        pydantic_parts = {}
        for part_name in self.results["character"]["parts"].keys():
            original_part = self.results["character"]["parts"][part_name]
            img_rel_path = (
                Path(original_part.get("image_path", "")).name
                if original_part.get("image_path")
                else ""
            )
            current_part_def = BODY_PARTS.get(part_name, {})

            pydantic_parts[part_name] = {
                "name": part_name,
                "roi": original_part.get("roi"),
                "image_path": img_rel_path,
                "fill_color": original_part.get("fill_color", "rgba(128,128,128,0.5)"),
                "local_pivot_offset": original_part.get("local_pivot_offset"),
                "z_value": float(original_part.get("z_value", 0.0)),
                "fixed": bool(original_part.get("fixed", False)),
                "anchor_joint_id": current_part_def.get("anchor_joint"),
            }

        character_name = (
            self.char_cfg.get("name", self.char_dir.name)
            if self.char_cfg
            else self.char_dir.name
        )

        output_data = {
            "character": {
                "name": character_name,
                "parts": pydantic_parts,
                "skeleton_joints": pydantic_skeleton_joints,
            }
        }

        parts_info_filepath = self.output_dir / "parts_info.json"
        with open(parts_info_filepath, "w") as f:
            json.dump(output_data, f, indent=4)


def main():
    parser = argparse.ArgumentParser(
        description="Extract character body parts using skeleton"
    )
    parser.add_argument("char_dir", help="Character directory path")
    parser.add_argument("--output", "-o", default=None, help="Output directory path")
    parser.add_argument(
        "--no-animation", action="store_true", help="Disable animation generation"
    )
    parser.add_argument("--frames", "-f", type=int, default=30, help="Animation frames")
    parser.add_argument("--fps", type=int, default=24, help="Animation FPS")

    args = parser.parse_args()

    extractor = BodyPartsExtractor(
        char_dir=args.char_dir,
        output_dir=args.output,
        generate_animations=not args.no_animation,
        num_frames=args.frames,
        fps=args.fps,
    )
    extractor.process()


if __name__ == "__main__":
    main()
