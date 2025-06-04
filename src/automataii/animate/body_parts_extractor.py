#!/usr/bin/env python

from typing import Optional, Dict, Any, List, Tuple
import cv2
import numpy as np
import yaml
import os
from pathlib import Path
import json
import argparse
from scipy.ndimage import distance_transform_edt, binary_dilation
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt
import logging
import random
from .body_parts_animation import deform_body_part, animate_body_part, save_animation, refine_mask_with_arap
import traceback
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import Qt
from .part_definitions import BODY_PARTS
from .templates import HTML_VIEWER_TEMPLATE, PART_CARD_TEMPLATE
from ..utils.helpers import NumpyEncoder
from ..utils.image_utils import save_image

def create_bone_mask(joint_map, start_joint, end_joint, mask_shape, thickness=20):
    """두 관절 사이의 뼈대 마스크를 생성합니다"""
    if start_joint not in joint_map or end_joint not in joint_map:
        return None

    # 빈 마스크 생성
    bone_mask = np.zeros(mask_shape, dtype=np.uint8)

    # 관절 위치
    start_pos = joint_map[start_joint]
    end_pos = joint_map[end_joint]

    # 선 길이 계산
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    line_length = np.sqrt(dx*dx + dy*dy)

    # 선 길이에 따라 두께 동적 조정 (긴 선은 더 두껍게)
    adjusted_thickness = int(thickness * (1.0 + line_length / 300))  # 300은 조정 인자

    # 선 그리기 (조정된 두께로 관절 연결)
    cv2.line(bone_mask, start_pos, end_pos, 255, adjusted_thickness)

    return bone_mask

def create_joint_mask(joint_map, joint_name, mask_shape, radius=30):
    """관절 주변의 마스크를 생성합니다"""
    if joint_name not in joint_map:
        return None

    # 빈 마스크 생성
    joint_mask = np.zeros(mask_shape, dtype=np.uint8)

    # 관절 위치
    pos = joint_map[joint_name]

    # 원 그리기 (관절 영역)
    cv2.circle(joint_mask, pos, radius, 255, -1)

    return joint_mask

def calculate_head_mask(joint_map, mask_shape, head_factor=2.2):
    """머리 영역의 마스크를 계산합니다 - 머리 전체 윤곽을 확보하도록 확장"""
    if 'neck' not in joint_map:
        return None

    neck_pos = joint_map['neck']

    # 목과 몸통 사이의 거리 계산 (torso가 없으면 대체 방법 사용)
    if 'torso' in joint_map:
        torso_pos = joint_map['torso']
        dx = neck_pos[0] - torso_pos[0]
        dy = neck_pos[1] - torso_pos[1]
        dist = np.sqrt(dx*dx + dy*dy)
    else:
        # 다른 관절들 간의 평균 거리를 사용하여 추정
        distances = []
        joints = list(joint_map.keys())
        for i in range(len(joints)):
            for j in range(i+1, len(joints)):
                if joints[i] != 'neck' and joints[j] != 'neck':  # 목 제외
                    pos1 = joint_map[joints[i]]
                    pos2 = joint_map[joints[j]]
                    d = np.sqrt((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2)
                    distances.append(d)

        if distances:
            dist = np.mean(distances) * 0.8  # 평균 관절 거리의 80%
        else:
            # 기본값: 마스크 높이의 1/6
            dist = mask_shape[0] / 6

    # 머리 중심 추정 - 더 위쪽으로 조정
    head_center_x = int(neck_pos[0])
    head_center_y = int(neck_pos[1] - dist * 0.7)  # 목 위쪽으로 더 많이 확장

    # 머리 크기 추정 (훨씬 더 크게 설정)
    head_radius = int(dist * head_factor)

    # 머리 마스크 생성 - 타원형을 더 넓게 (특히 가로 방향)
    head_mask = np.zeros(mask_shape, dtype=np.uint8)
    axes_length = (int(head_radius * 1.1), int(head_radius * 1.2))  # 가로, 세로 반경 확장
    cv2.ellipse(head_mask, (head_center_x, head_center_y), axes_length,
                0, 0, 360, 255, -1)  # 타원 그리기

    return head_mask

def create_part_mask(char_mask, joint_map, part_def, mask_shape):
    """신체 부위의 마스크를 생성합니다"""
    # 특별 케이스: 머리 (윤곽선을 모두 포함하도록 확장)
    if 'head' in part_def:
        head_mask = calculate_head_mask(joint_map, mask_shape)
        if head_mask is not None:
            # 머리 마스크 대폭 확장 (귀, 코 등 모든 특징을 포함하도록)
            kernel = np.ones((11, 11), np.uint8)
            head_mask = cv2.dilate(head_mask, kernel, iterations=3)

            # 캐릭터 전체 윤곽선 확보를 위한 추가 처리
            # 머리 영역 근처에서 캐릭터 마스크 가장자리 추출
            edge_kernel = np.ones((3, 3), np.uint8)
            char_edge = cv2.Canny(char_mask, 100, 200)
            char_edge = cv2.dilate(char_edge, edge_kernel, iterations=1)

            # 머리 마스크와 가까운 모든 윤곽선 병합
            head_dilated_for_edge = cv2.dilate(head_mask, kernel, iterations=2)
            nearby_edges = cv2.bitwise_and(char_edge, head_dilated_for_edge)

            # 윤곽선 영역 채우기 및 병합
            if np.any(nearby_edges):
                edges_dilated = cv2.dilate(nearby_edges, kernel, iterations=2)
                head_mask = cv2.bitwise_or(head_mask, edges_dilated)

            # 캐릭터 마스크와 교차하여 실제 영역만 유지
            head_mask = cv2.bitwise_and(head_mask, char_mask)
        return head_mask

    # 관절 위치와 뼈대 마스크 생성
    joints = part_def['joints']
    part_mask = np.zeros(mask_shape, dtype=np.uint8)

    # 부위에 따라 다른 두께와 확장 계수 사용
    thickness = 20  # 기본 두께
    joint_radius = 30  # 기본 관절 반경
    dilation_iterations = 3  # 기본 팽창 반복 횟수

    # 부위별 특성화
    if 'head' in part_def:
        thickness = 35  # 머리는 더 두껍게
        joint_radius = 50  # 머리 관절은 훨씬 크게
        dilation_iterations = 5  # 머리는 더 많이 팽창
    elif any(term in part_def.get('name', '') for term in ['torso']):
        thickness = 30  # 몸통은 더 두껍게
        joint_radius = 40
        dilation_iterations = 4
    elif any(term in part_def.get('name', '') for term in ['arm', 'leg']):
        thickness = 25  # 팔다리는 중간 정도 두께
        dilation_iterations = 3
    elif any(term in part_def.get('name', '') for term in ['hand', 'foot']):
        joint_radius = 35  # 팔다리 끝은 관절 크게
        dilation_iterations = 4

    # 여러 관절 쌍 처리
    if len(joints) > 2:
        # 왼쪽 관절 쌍과 오른쪽 관절 쌍을 별도로 처리
        pairs = []
        # 왼쪽 관절 쌍
        left_joints = [j for j in joints if j.startswith('left_')]
        if len(left_joints) >= 2:
            for i in range(len(left_joints) - 1):
                pairs.append((left_joints[i], left_joints[i+1]))

        # 오른쪽 관절 쌍
        right_joints = [j for j in joints if j.startswith('right_')]
        if len(right_joints) >= 2:
            for i in range(len(right_joints) - 1):
                pairs.append((right_joints[i], right_joints[i+1]))

        # 일반 관절 쌍 (left/right 접두사가 없는 경우)
        general_joints = [j for j in joints if not (j.startswith('left_') or j.startswith('right_'))]
        if len(general_joints) >= 2:
            for i in range(len(general_joints) - 1):
                pairs.append((general_joints[i], general_joints[i+1]))

        # 각 관절 쌍에 대해 뼈대 마스크 생성
        for start_joint, end_joint in pairs:
            bone_mask = create_bone_mask(joint_map, start_joint, end_joint, mask_shape, thickness=thickness)
            if bone_mask is not None:
                part_mask = cv2.bitwise_or(part_mask, bone_mask)
    else:
        # 기존 로직: 연속된 관절 연결
        for i in range(len(joints) - 1):
            bone_mask = create_bone_mask(joint_map, joints[i], joints[i+1], mask_shape, thickness=thickness)
            if bone_mask is not None:
                part_mask = cv2.bitwise_or(part_mask, bone_mask)

    # 추가적인 관절 영역
    for joint in joints:
        joint_mask = create_joint_mask(joint_map, joint, mask_shape, radius=joint_radius)
        if joint_mask is not None:
            part_mask = cv2.bitwise_or(part_mask, joint_mask)

    # 팽창 연산으로 마스크 확장
    kernel = np.ones((5, 5), np.uint8)
    part_mask = cv2.dilate(part_mask, kernel, iterations=dilation_iterations)

    # 캐릭터 마스크와 교차하여 실제 영역만 가져오기
    part_mask = cv2.bitwise_and(part_mask, char_mask)

    # 거리 변환을 사용하여 뼈대 주변으로 점진적 영역 확장
    dist_from_part = distance_transform_edt(255 - part_mask)
    expanded_mask = np.zeros_like(part_mask)
    expanded_mask[dist_from_part <= 10] = 255  # 뼈대에서 10픽셀 거리까지 확장

    # 확장된 마스크와 원본 마스크 결합
    part_mask = cv2.bitwise_or(part_mask, expanded_mask)
    part_mask = cv2.bitwise_and(part_mask, char_mask)  # 캐릭터 내부로 제한

    return part_mask

def segment_body_parts(texture, character_mask, joint_map, parts_def):
    """전체 마스크를 신체 부위별로 분할합니다 (ARAP으로 개선된 방식)"""
    height, width = character_mask.shape
    mask_shape = (height, width)
    logging.info("Segmenting body parts using improved ARAP-based algorithm...")

    # 1. 각 부위별 초기 마스크 생성 (create_part_mask 사용)
    initial_part_masks = {}
    for part_name, part_def in parts_def.items():
        initial_mask = create_part_mask(character_mask, joint_map, part_def, mask_shape)
        if initial_mask is None:
            initial_mask = np.zeros(mask_shape, dtype=np.uint8)

        # 마스크가 너무 작으면 먼저 팽창시켜 확장
        if np.sum(initial_mask) < 1000:
            kernel = np.ones((5, 5), np.uint8)
            initial_mask = cv2.dilate(initial_mask, kernel, iterations=2)
            initial_mask = cv2.bitwise_and(initial_mask, character_mask)  # 캐릭터 내부로 제한

        initial_part_masks[part_name] = initial_mask
        logging.debug(f"Generated initial mask for {part_name} with {np.count_nonzero(initial_mask)} pixels")

    # 2. Watershed를 위한 마커 준비
    markers = np.zeros(mask_shape, dtype=np.int32)
    marker_id = 1
    sure_fg_total = np.zeros(mask_shape, dtype=np.uint8) # 모든 확실한 전경 영역 결합

    part_name_map = {} # marker_id -> part_name
    for part_name, initial_mask in initial_part_masks.items():
        if np.any(initial_mask):
            # 마스크 침식하여 확실한 전경 영역 찾기 (겹침 제거 도움)
            kernel = np.ones((3,3), np.uint8)
            sure_fg = cv2.erode(initial_mask, kernel, iterations=1)

            # 라벨링 (다른 부분과 겹치지 않도록 현재 마커 영역만 사용)
            markers[sure_fg > 0] = marker_id
            part_name_map[marker_id] = part_name
            sure_fg_total = cv2.bitwise_or(sure_fg_total, sure_fg)
            logging.debug(f"Assigned marker ID {marker_id} to {part_name}")
            marker_id += 1
        else:
             logging.warning(f"Initial mask for {part_name} is empty. Skipping marker.")

    # 알 수 없는 영역 계산 (캐릭터 마스크 - 확실한 전경)
    unknown = cv2.subtract(character_mask, sure_fg_total)
    markers[unknown > 0] = 0 # 알 수 없는 영역은 0으로 표시

    logging.debug(f"Total markers created: {marker_id - 1}")

    # 3. Watershed를 위한 이미지 준비 (마스크 사용으로 복귀)
    img_for_watershed = cv2.cvtColor(character_mask, cv2.COLOR_GRAY2BGR)
    logging.debug("Prepared 3-channel image for watershed from character mask.")

    # 4. Watershed 실행
    logging.info("Running Watershed...")
    cv2.watershed(img_for_watershed, markers)
    logging.info("Watershed complete.")

    # 5. 최종 부위별 마스크 생성
    final_part_masks = {}
    for m_id, part_name in part_name_map.items():
        # Watershed 결과에서 해당 마커 ID를 가진 픽셀 선택
        part_mask = np.zeros(mask_shape, dtype=np.uint8)
        part_mask[markers == m_id] = 255

        # 원본 캐릭터 마스크와 교차하여 배경 픽셀 제거
        part_mask = cv2.bitwise_and(part_mask, character_mask)

        # 마스크에 구멍이 있으면 채우기
        contours, _ = cv2.findContours(part_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            filled_mask = np.zeros_like(part_mask)
            cv2.fillPoly(filled_mask, contours, 255)
            part_mask = filled_mask

        # 작은 홀 채우기 - 먼저 수행해서 ARAP에 더 나은 마스크 제공
        kernel = np.ones((5, 5), np.uint8)
        part_mask = cv2.morphologyEx(part_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # ARAP을 사용하여 최종 마스크 다시 한번 개선 (경계 더 자연스럽게)
        part_mask = cv2.bitwise_and(part_mask, character_mask)

        final_part_masks[part_name] = part_mask
        logging.debug(f"Generated final mask for {part_name} with {np.count_nonzero(part_mask)} pixels")

    # 모든 부위 마스크의 합집합
    all_parts_mask = np.zeros_like(character_mask)
    for mask in final_part_masks.values():
        all_parts_mask = cv2.bitwise_or(all_parts_mask, mask)

    # 할당되지 않은 픽셀 처리 (가장 가까운 부위에 할당)
    unassigned = cv2.subtract(character_mask, all_parts_mask)
    if np.any(unassigned):
        # 할당되지 않은 영역 연결 컴포넌트 분석
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(unassigned, connectivity=8)

        dist_maps = {}
        for part_name, mask in final_part_masks.items():
            # 각 부위에 대한 거리 맵 계산
            dist_map = distance_transform_edt(255 - mask)
            dist_maps[part_name] = dist_map

        # 각 연결 컴포넌트를 가장 가까운 부위에 할당
        for label in range(1, num_labels):  # 0은 배경
            component_size = stats[label, cv2.CC_STAT_AREA]
            if component_size < 10:  # 너무 작은 컴포넌트는 무시
                continue

            # 컴포넌트의 중심점
            cx, cy = centroids[label]
            cx, cy = int(cx), int(cy)

            # 가장 가까운 부위 찾기
            min_dist = float('inf')
            closest_part = None
            for part_name, dist_map in dist_maps.items():
                # 컴포넌트 내 모든 픽셀의 평균 거리 계산
                component_pixels = (labels == label)
                if np.any(component_pixels):
                    avg_dist = np.mean(dist_map[component_pixels])
                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        closest_part = part_name

            # 해당 컴포넌트를 가장 가까운 부위에 할당
            if closest_part:
                final_part_masks[closest_part][labels == label] = 255

        # 남은 할당되지 않은 픽셀 처리
        unassigned = cv2.subtract(character_mask, all_parts_mask)
        if np.any(unassigned):
            # 개별 픽셀 처리
            y_coords, x_coords = np.where(unassigned > 0)
            for y, x in zip(y_coords, x_coords):
                min_dist = float('inf')
                closest_part = None
                for part_name, dist_map in dist_maps.items():
                    if dist_map[y, x] < min_dist:
                        min_dist = dist_map[y, x]
                        closest_part = part_name

                if closest_part:
                    final_part_masks[closest_part][y, x] = 255

    # 최종 후처리: 각 마스크에 작은 메달 연산 적용하여 경계 부드럽게
    for part_name in final_part_masks:
        mask = final_part_masks[part_name]
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)  # 작은 노이즈 제거
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)  # 작은 구멍 채우기
        final_part_masks[part_name] = mask

    return final_part_masks

def visualize_segmentation(mask, part_masks, joint_map, output_path):
    """분할 결과를 시각화합니다"""
    # 컬러 이미지 생성
    height, width = mask.shape
    vis_image = np.zeros((height, width, 3), dtype=np.uint8)

    # 각 부위별 색상 지정
    colors = {
        'head': (255, 0, 0),        # 빨강
        'torso': (0, 255, 0),       # 초록
        'left_arm_upper': (0, 0, 255),    # 파랑
        'left_arm_lower': (255, 255, 0),  # 노랑
        'right_arm_upper': (255, 0, 255),  # 마젠타
        'right_arm_lower': (0, 255, 255),  # 시안
        'left_leg_upper': (128, 0, 0),    # 빨강
        'left_leg_lower': (0, 128, 0),    # 초록
        'right_leg_upper': (0, 0, 128),    # 파랑
        'right_leg_lower': (128, 128, 0),  # 노랑
    }

    # 각 부위별 마스크 적용
    for part_name, part_mask in part_masks.items():
        if part_name in colors:
            color = colors[part_name]
            colored_mask = np.zeros((height, width, 3), dtype=np.uint8)
            colored_mask[part_mask > 0] = color
            vis_image = cv2.addWeighted(vis_image, 1.0, colored_mask, 0.5, 0)

    # 관절 위치 표시
    for joint_name, joint_pos in joint_map.items():
        cv2.circle(vis_image, joint_pos, 5, (255, 255, 255), -1)
        cv2.putText(vis_image, joint_name, (joint_pos[0]+5, joint_pos[1]-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # 이미지 저장
    cv2.imwrite(output_path, vis_image)

class BodyPartsExtractor:
    def __init__(self, char_dir: str, output_dir: Optional[str] = None,
                 generate_animations: bool = False, num_frames: int = 30, fps: int = 24):
        self.char_dir = Path(char_dir)
        self.output_dir = Path(output_dir) # Use the provided output_dir directly
        self.generate_animations = generate_animations
        self.num_frames = num_frames
        self.fps = fps

        # Initialize instance variables that will be populated during processing
        self.char_cfg: Optional[Dict[str, Any]] = None
        self.texture: Optional[np.ndarray] = None
        self.mask: Optional[np.ndarray] = None
        self.texture_relative_joint_map: Optional[Dict[str, Tuple[int, int]]] = None
        self.part_masks: Optional[Dict[str, np.ndarray]] = None
        self.results: Optional[Dict[str, Any]] = None
        self.image_height: Optional[int] = None
        self.image_width: Optional[int] = None

    def _read_char_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        """Reads character configuration file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error(f"Character config file not found: {config_path}")
        except yaml.YAMLError as e:
            logging.error(f"Error parsing character config {config_path}: {e}")
        return None

    def _create_joint_map(self, skeleton: List[Dict[str, Any]]) -> Dict[str, Tuple[int, int]]:
        """Creates a mapping from joint names to locations."""
        joint_map = {}
        for joint in skeleton:
            joint_map[joint['name']] = tuple(joint['loc'])
        return joint_map

    def _get_proximal_joint_name(self, part_name: str, part_definition: Dict[str, Any]) -> Optional[str]:
        """Determines the proximal joint name for a given part."""
        if part_name == 'head':
            return 'neck'
        if part_name == 'torso':
            # Torso is often the root or its pivot is the 'torso' joint itself.
            # Returning None as it doesn't rotate around a *more* proximal single joint in many contexts.
            return None

        joints = part_definition.get('joints')
        if joints and isinstance(joints, list) and len(joints) > 0:
            # Assuming the first joint in the list is the most proximal
            return joints[0]
        else:
            logging.warning(f"Could not determine proximal joint for {part_name}: No joints defined or invalid format.")
            return None

    def _load_initial_data(self) -> bool:
        """Loads character configuration, texture, and mask."""
        char_cfg_path = os.path.join(self.char_dir, 'char_cfg.yaml')
        texture_path = os.path.join(self.char_dir, 'texture.png')
        mask_path = os.path.join(self.char_dir, 'mask.png')

        if not all(os.path.exists(p) for p in [char_cfg_path, texture_path, mask_path]):
            logging.error(f"Required files not found in: {self.char_dir}")
            return False

        self.char_cfg = self._read_char_config(char_cfg_path)
        self.texture = cv2.imread(texture_path, cv2.IMREAD_UNCHANGED)
        self.mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        if self.char_cfg is None or self.texture is None or self.mask is None:
            logging.error(f"Failed to load one or more essential files from {self.char_dir}")
            return False

        self.image_height = self.char_cfg['height']
        self.image_width = self.char_cfg['width']
        return True

    def _prepare_joint_map(self):
        """Prepares the texture-relative joint map."""
        if not self.char_cfg:
            logging.error("Character config not loaded for joint map preparation.")
            return

        # original_joint_map의 'loc' 좌표는 char_cfg.yaml에서 오며,
        # image_to_annotations.py에 의해 'cropped' 이미지 기준으로 저장됩니다.
        # 따라서 이 좌표가 이미 최종 텍스처 기준 좌표입니다.
        self.texture_relative_joint_map = self._create_joint_map(self.char_cfg['skeleton'])
        logging.debug(f"Texture-relative joint map (should be same as original from char_cfg): {self.texture_relative_joint_map}")

        # bounding_box.yaml의 offset 정보는 여기서는 직접 사용하지 않습니다.
        # 해당 정보는 텍스처 자체의 원본 위치를 알 때 필요할 수 있으나,
        # 조인트 좌표는 이미 텍스처(cropped 이미지) 기준으로 char_cfg에 저장됩니다.
        bounding_box_path = self.char_dir / 'bounding_box.yaml'
        if bounding_box_path.exists():
            try:
                with open(bounding_box_path, 'r') as f:
                    bbox_data = yaml.safe_load(f)
                if isinstance(bbox_data, dict) and 'left' in bbox_data and 'top' in bbox_data:
                    # 이 offset 정보는 로깅 또는 다른 용도로는 사용할 수 있습니다.
                    logging.info(f"Bounding box offset from bounding_box.yaml: left={bbox_data['left']}, top={bbox_data['top']} (This offset is NOT applied to joint coordinates here as they are already texture-relative).")
            except Exception as e:
                logging.warning(f"Error loading bounding_box.yaml: {e}. This does not affect joint map calculation if char_cfg is correct.")
        else:
            logging.info(f"bounding_box.yaml not found. This is acceptable if char_cfg contains texture-relative joint coordinates.")

    def _create_bone_mask(self, start_joint_name: str, end_joint_name: str, mask_shape: Tuple[int, int], thickness: int = 20) -> Optional[np.ndarray]:
        """두 관절 사이의 뼈대 마스크를 생성합니다"""
        if self.texture_relative_joint_map is None:
            logging.error("Joint map not initialized for bone mask creation.")
            return None
        if start_joint_name not in self.texture_relative_joint_map or end_joint_name not in self.texture_relative_joint_map:
            logging.warning(f"Joints {start_joint_name} or {end_joint_name} not in joint_map.")
            return None

        bone_mask = np.zeros(mask_shape, dtype=np.uint8)
        start_pos = self.texture_relative_joint_map[start_joint_name]
        end_pos = self.texture_relative_joint_map[end_joint_name]

        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        line_length = np.sqrt(dx*dx + dy*dy)
        adjusted_thickness = int(thickness * (1.0 + line_length / 300))
        cv2.line(bone_mask, start_pos, end_pos, 255, adjusted_thickness)
        return bone_mask

    def _create_joint_mask(self, joint_name: str, mask_shape: Tuple[int, int], radius: int = 30) -> Optional[np.ndarray]:
        """관절 주변의 마스크를 생성합니다"""
        if self.texture_relative_joint_map is None:
            logging.error("Joint map not initialized for joint mask creation.")
            return None
        if joint_name not in self.texture_relative_joint_map:
            logging.warning(f"Joint {joint_name} not in joint_map.")
            return None

        joint_mask_np = np.zeros(mask_shape, dtype=np.uint8) # Renamed to avoid conflict
        pos = self.texture_relative_joint_map[joint_name]
        cv2.circle(joint_mask_np, pos, radius, 255, -1)
        return joint_mask_np

    def _calculate_head_mask(self, mask_shape: Tuple[int, int], head_factor: float = 2.2) -> Optional[np.ndarray]:
        """머리 영역의 마스크를 계산합니다 - 머리 전체 윤곽을 확보하도록 확장"""
        if self.texture_relative_joint_map is None or 'neck' not in self.texture_relative_joint_map:
            logging.warning("Neck joint not found in joint_map for head mask calculation.")
            return None

        neck_pos = self.texture_relative_joint_map['neck']
        dist = 0
        if 'torso' in self.texture_relative_joint_map:
            torso_pos = self.texture_relative_joint_map['torso']
            dx = neck_pos[0] - torso_pos[0]
            dy = neck_pos[1] - torso_pos[1]
            dist = np.sqrt(dx*dx + dy*dy)
        else:
            distances = []
            joints_available = list(self.texture_relative_joint_map.keys())
            for i in range(len(joints_available)):
                for j in range(i + 1, len(joints_available)):
                    if joints_available[i] != 'neck' and joints_available[j] != 'neck':
                        pos1 = self.texture_relative_joint_map[joints_available[i]]
                        pos2 = self.texture_relative_joint_map[joints_available[j]]
                        d = np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
                        distances.append(d)
            if distances:
                dist = np.mean(distances) * 0.8
            else:
                dist = mask_shape[0] / 6

        head_center_x = int(neck_pos[0])
        head_center_y = int(neck_pos[1] - dist * 0.7)
        head_radius = int(dist * head_factor)
        head_mask_np = np.zeros(mask_shape, dtype=np.uint8) # Renamed
        axes_length = (int(head_radius * 1.1), int(head_radius * 1.2))
        cv2.ellipse(head_mask_np, (head_center_x, head_center_y), axes_length, 0, 0, 360, 255, -1)
        return head_mask_np

    def _create_part_mask(self, part_name_key: str, part_def_data: Dict[str, Any], mask_shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """신체 부위의 마스크를 생성합니다. `part_name_key`는 BODY_PARTS의 키입니다."""
        if self.mask is None or self.texture_relative_joint_map is None:
            logging.error("Character mask or joint map not initialized for part mask creation.")
            return None

        # 특별 케이스: 머리 (윤곽선을 모두 포함하도록 확장)
        # The part_def_data might not have 'name' if it's directly from BODY_PARTS. Use part_name_key for logic.
        if part_name_key == 'head': # Check against the key used for BODY_PARTS
            head_mask_val = self._calculate_head_mask(mask_shape) # Renamed
            if head_mask_val is not None:
                kernel = np.ones((11, 11), np.uint8)
                head_mask_val = cv2.dilate(head_mask_val, kernel, iterations=3)
                edge_kernel = np.ones((3, 3), np.uint8)
                char_edge = cv2.Canny(self.mask, 100, 200)
                char_edge = cv2.dilate(char_edge, edge_kernel, iterations=1)
                head_dilated_for_edge = cv2.dilate(head_mask_val, kernel, iterations=2)
                nearby_edges = cv2.bitwise_and(char_edge, head_dilated_for_edge)
                if np.any(nearby_edges):
                    edges_dilated = cv2.dilate(nearby_edges, kernel, iterations=2)
                    head_mask_val = cv2.bitwise_or(head_mask_val, edges_dilated)
                head_mask_val = cv2.bitwise_and(head_mask_val, self.mask)
            return head_mask_val

        joints = part_def_data['joints']
        part_mask_np = np.zeros(mask_shape, dtype=np.uint8) # Renamed

        thickness = 20
        joint_radius = 30
        dilation_iterations = 3

        # part_name_key is used here for checking part type
        if part_name_key == 'head':
            thickness = 35
            joint_radius = 50
            dilation_iterations = 5
        elif 'torso' in part_name_key: # Check if 'torso' is part of the key
            thickness = 30
            joint_radius = 40
            dilation_iterations = 4
        elif any(term in part_name_key for term in ['arm', 'leg']):
            thickness = 25
            dilation_iterations = 3
        elif any(term in part_name_key for term in ['hand', 'foot']):
            joint_radius = 35
            dilation_iterations = 4

        if len(joints) > 2:
            pairs = []
            left_joints = [j for j in joints if j.startswith('left_')]
            if len(left_joints) >= 2:
                for i in range(len(left_joints) - 1):
                    pairs.append((left_joints[i], left_joints[i+1]))
            right_joints = [j for j in joints if j.startswith('right_')]
            if len(right_joints) >= 2:
                for i in range(len(right_joints) - 1):
                    pairs.append((right_joints[i], right_joints[i+1]))
            general_joints = [j for j in joints if not (j.startswith('left_') or j.startswith('right_'))]
            if len(general_joints) >= 2:
                for i in range(len(general_joints) - 1):
                    pairs.append((general_joints[i], general_joints[i+1]))
            for start_joint, end_joint in pairs:
                bone_mask = self._create_bone_mask(start_joint, end_joint, mask_shape, thickness=thickness)
                if bone_mask is not None:
                    part_mask_np = cv2.bitwise_or(part_mask_np, bone_mask)
        else:
            for i in range(len(joints) - 1):
                bone_mask = self._create_bone_mask(joints[i], joints[i+1], mask_shape, thickness=thickness)
                if bone_mask is not None:
                    part_mask_np = cv2.bitwise_or(part_mask_np, bone_mask)

        for joint in joints:
            joint_mask_val = self._create_joint_mask(joint, mask_shape, radius=joint_radius) # Renamed
            if joint_mask_val is not None:
                part_mask_np = cv2.bitwise_or(part_mask_np, joint_mask_val)

        kernel = np.ones((5, 5), np.uint8)
        part_mask_np = cv2.dilate(part_mask_np, kernel, iterations=dilation_iterations)
        part_mask_np = cv2.bitwise_and(part_mask_np, self.mask)
        dist_from_part = distance_transform_edt(255 - part_mask_np)
        expanded_mask = np.zeros_like(part_mask_np)
        expanded_mask[dist_from_part <= 10] = 255
        part_mask_np = cv2.bitwise_or(part_mask_np, expanded_mask)
        part_mask_np = cv2.bitwise_and(part_mask_np, self.mask)
        return part_mask_np

    def _segment_body_parts(self) -> Dict[str, np.ndarray]:
        """전체 마스크를 신체 부위별로 분할합니다 (ARAP으로 개선된 방식)"""
        if self.mask is None or self.texture_relative_joint_map is None or self.texture is None:
            logging.error("Essential data (mask, joint_map, or texture) not initialized for segmentation.")
            return {}

        height, width = self.mask.shape
        mask_shape = (height, width)
        logging.info("Segmenting body parts using improved ARAP-based algorithm...")

        initial_part_masks = {}
        for part_name, part_def in BODY_PARTS.items(): # BODY_PARTS is globally available
            initial_mask = self._create_part_mask(part_name, part_def, mask_shape)
            if initial_mask is None:
                initial_mask = np.zeros(mask_shape, dtype=np.uint8)
            if np.sum(initial_mask) < 1000: # Ensure self.mask is used for bitwise_and
                kernel = np.ones((5, 5), np.uint8)
                initial_mask = cv2.dilate(initial_mask, kernel, iterations=2)
                initial_mask = cv2.bitwise_and(initial_mask, self.mask)
            initial_part_masks[part_name] = initial_mask
            logging.debug(f"Generated initial mask for {part_name} with {np.count_nonzero(initial_mask)} pixels")

        markers = np.zeros(mask_shape, dtype=np.int32)
        marker_id = 1
        sure_fg_total = np.zeros(mask_shape, dtype=np.uint8)
        part_name_map = {}
        for part_name, initial_mask_val in initial_part_masks.items(): # Renamed initial_mask
            if np.any(initial_mask_val):
                kernel = np.ones((3,3), np.uint8)
                sure_fg = cv2.erode(initial_mask_val, kernel, iterations=1)
                markers[sure_fg > 0] = marker_id
                part_name_map[marker_id] = part_name
                sure_fg_total = cv2.bitwise_or(sure_fg_total, sure_fg)
                logging.debug(f"Assigned marker ID {marker_id} to {part_name}")
                marker_id += 1
            else:
                 logging.warning(f"Initial mask for {part_name} is empty. Skipping marker.")

        unknown = cv2.subtract(self.mask, sure_fg_total)
        markers[unknown > 0] = 0
        logging.debug(f"Total markers created: {marker_id - 1}")

        img_for_watershed = cv2.cvtColor(self.mask, cv2.COLOR_GRAY2BGR)
        logging.debug("Prepared 3-channel image for watershed from character mask.")
        logging.info("Running Watershed...")
        cv2.watershed(img_for_watershed, markers)
        logging.info("Watershed complete.")

        final_part_masks = {}
        for m_id, part_name in part_name_map.items():
            part_mask_seg = np.zeros(mask_shape, dtype=np.uint8)
            part_mask_seg[markers == m_id] = 255

            # 원본 캐릭터 마스크와 교차하여 배경 픽셀 제거
            part_mask_seg = cv2.bitwise_and(part_mask_seg, self.mask)

            # 마스크에 구멍이 있으면 채우기
            contours, _ = cv2.findContours(part_mask_seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                filled_mask = np.zeros_like(part_mask_seg)
                cv2.fillPoly(filled_mask, contours, 255)
                part_mask_seg = filled_mask

            # 작은 홀 채우기 - 먼저 수행해서 ARAP에 더 나은 마스크 제공
            kernel = np.ones((5, 5), np.uint8)
            part_mask_seg = cv2.morphologyEx(part_mask_seg, cv2.MORPH_CLOSE, kernel, iterations=2)

            # ARAP을 사용하여 최종 마스크 다시 한번 개선 (경계 더 자연스럽게)
            part_mask_seg = cv2.bitwise_and(part_mask_seg, self.mask)

            final_part_masks[part_name] = part_mask_seg
            logging.debug(f"Generated final mask for {part_name} with {np.count_nonzero(part_mask_seg)} pixels")

        all_parts_mask = np.zeros_like(self.mask)
        for mask in final_part_masks.values():
            all_parts_mask = cv2.bitwise_or(all_parts_mask, mask)

        unassigned = cv2.subtract(self.mask, all_parts_mask)
        if np.any(unassigned):
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(unassigned, connectivity=8)
            dist_maps = {}
            for part_name, mask in final_part_masks.items():
                dist_map = distance_transform_edt(255 - mask)
                dist_maps[part_name] = dist_map
            for label in range(1, num_labels):
                component_size = stats[label, cv2.CC_STAT_AREA]
                if component_size < 10:
                    continue
                cx, cy = centroids[label]
                cx, cy = int(cx), int(cy)
                min_dist = float('inf')
                closest_part = None
                for part_name, dist_map in dist_maps.items():
                    component_pixels = (labels == label)
                    if np.any(component_pixels):
                        avg_dist = np.mean(dist_map[component_pixels])
                        if avg_dist < min_dist:
                            min_dist = avg_dist
                            closest_part = part_name
                if closest_part:
                    final_part_masks[closest_part][labels == label] = 255

        for part_name in final_part_masks:
            mask = final_part_masks[part_name]
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            final_part_masks[part_name] = mask
        return final_part_masks

    def _visualize_segmentation(self):
        """분할 결과를 시각화합니다"""
        if self.mask is None or not self.part_masks or self.texture_relative_joint_map is None:
            logging.error("Essential data not available for visualizing segmentation.")
            return

        output_path = os.path.join(self.output_dir, 'segmentation_vis.png')
        height, width = self.mask.shape
        vis_image = np.zeros((height, width, 3), dtype=np.uint8)

        colors = {
            'head': (255, 0, 0), 'torso': (0, 255, 0),
            'left_arm_upper': (0, 0, 255), 'left_arm_lower': (255, 255, 0),
            'right_arm_upper': (255, 0, 255), 'right_arm_lower': (0, 255, 255),
            'left_leg_upper': (128, 0, 0), 'left_leg_lower': (0, 128, 0),
            'right_leg_upper': (0, 0, 128), 'right_leg_lower': (128, 128, 0),
        }

        for part_name, part_mask in self.part_masks.items():
            if part_name in colors:
                color = colors[part_name]
                colored_mask = np.zeros((height, width, 3), dtype=np.uint8)
                colored_mask[part_mask > 0] = color
                vis_image = cv2.addWeighted(vis_image, 1.0, colored_mask, 0.5, 0)

        for joint_name, joint_pos in self.texture_relative_joint_map.items():
            cv2.circle(vis_image, joint_pos, 5, (255, 255, 255), -1)
            cv2.putText(vis_image, joint_name, (joint_pos[0]+5, joint_pos[1]-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        try:
            cv2.imwrite(output_path, vis_image)
            logging.info(f"Segmentation visualization saved to {output_path}")
        except Exception as e:
            logging.error(f"Failed to save segmentation visualization: {e}")

    def _generate_html_viewer(self):
        """HTML 뷰어를 생성합니다"""
        if not self.results or 'character' not in self.results or 'parts' not in self.results['character']:
            logging.error("Results not available or incomplete for HTML viewer generation.")
            return

        part_cards = ""
        for part_name, part_info in self.results['character']['parts'].items():
            image_path = os.path.basename(part_info.get('image_path', '')) # Use .get for safety
            svg_path = os.path.basename(part_info.get('svg_path', '')) # Use .get for safety, will be empty string if key missing
            animation_element = ""
            if 'animations' in self.results['character'] and part_name in self.results['character']['animations']:
                animation_path = os.path.basename(self.results['character']['animations'][part_name]['animation_path'])
                animation_element = f'<div class="animation-container"><h4>Animation</h4><img src="{animation_path}" alt="{part_name} Animation" class="part-animation"></div>'
            part_card = PART_CARD_TEMPLATE.format(
                part_name=part_name.replace('_', ' ').title(),
                image_path=image_path,
                svg_path=svg_path,
                animation_element=animation_element
            )
            part_cards += part_card

        texture_path = os.path.relpath(os.path.join(self.char_dir, 'image.png'), self.output_dir)
        segmentation_path = "segmentation_vis.png"
        html_content = HTML_VIEWER_TEMPLATE.format(
            texture_path=texture_path,
            segmentation_path=segmentation_path,
            part_cards=part_cards
        )
        html_output_path = os.path.join(self.output_dir, 'viewer.html')
        try:
            with open(html_output_path, 'w') as f:
                f.write(html_content)
            logging.info(f"HTML viewer generated: {html_output_path}")
        except IOError as e:
            logging.error(f"Failed to write HTML viewer: {e}")

    def _extract_body_part(self, full_texture: np.ndarray, part_mask_data: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        """Extracts the part texture, creates an alpha channel, and finds the bounding box."""
        if part_mask_data is None or np.sum(part_mask_data) == 0:
            logging.warning("Empty or None mask provided to _extract_body_part.")
            return None, None, None

        # Ensure mask is boolean for findContours
        if part_mask_data.dtype != np.uint8:
            part_mask_data = part_mask_data.astype(np.uint8)

        # Find contours to get the bounding box
        contours, _ = cv2.findContours(part_mask_data, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logging.warning("No contours found in part_mask_data.")
            return None, None, None

        # Assuming the largest contour corresponds to the part
        main_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(main_contour)

        if w == 0 or h == 0:
            logging.warning(f"Zero width or height bounding box for a part. Mask sum: {np.sum(part_mask_data)}")
            # Create a minimal 1x1 texture to avoid errors downstreams if needed
            # return np.zeros((1, 1, 3), dtype=np.uint8), np.zeros((1, 1), dtype=np.uint8), (x,y,1,1)
            return None, None, None


        # Extract the part texture using the bounding box
        part_texture_cropped = full_texture[y:y+h, x:x+w]

        # Create an alpha channel from the mask (cropped to the bounding box)
        alpha_channel_cropped = part_mask_data[y:y+h, x:x+w]
        alpha_channel_cropped = np.where(alpha_channel_cropped > 0, 255, 0).astype(np.uint8)

        if part_texture_cropped.shape[:2] != alpha_channel_cropped.shape[:2]:
            logging.error(f"Shape mismatch! Texture: {part_texture_cropped.shape[:2]}, Alpha: {alpha_channel_cropped.shape[:2]}. ROI: ({x},{y},{w},{h})")
            # This case should ideally not happen if ROI is correct
            # Fallback: resize alpha to match texture (less ideal, check ROI logic)
            alpha_channel_cropped = cv2.resize(alpha_channel_cropped, (part_texture_cropped.shape[1], part_texture_cropped.shape[0]), interpolation=cv2.INTER_NEAREST)


        logging.debug(f"Extracted part with ROI: x={x}, y={y}, w={w}, h={h}. Texture shape: {part_texture_cropped.shape}, Alpha shape: {alpha_channel_cropped.shape}")
        return part_texture_cropped, alpha_channel_cropped, (x, y, w, h)

    def process(self):
        """메인 처리 함수: 파트 분할, SVG 생성, 애니메이션 (선택적)."""
        if not self._load_initial_data():
            return

        self._prepare_joint_map()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.part_masks = self._segment_body_parts()

        if not self.part_masks:
            logging.error("Body part segmentation failed.")
            return

        self._visualize_segmentation()

        self.results = {
            'character': {
                'width': int(self.image_width) if self.image_width else 0,
                'height': int(self.image_height) if self.image_height else 0,
                'parts': {},
                'joint_map': self.texture_relative_joint_map if self.texture_relative_joint_map else {},
                'skeleton': self.char_cfg.get('skeleton', []) if self.char_cfg else [],
                'animations': {}
            }
        }

        for part_name, part_mask_data in self.part_masks.items():
            logging.info(f"Processing part: {part_name}")

            part_image_texture, _part_mask_roi_not_used, part_bbox_coords = self._extract_body_part(
                self.texture, part_mask_data
            )

            if part_image_texture is None or part_bbox_coords is None:
                logging.warning(f"Could not extract texture or bounding box for part '{part_name}'. Skipping.")
                continue

            roi_x, roi_y, roi_w, roi_h = part_bbox_coords

            # PNG 이미지 저장
            png_file_path = self.output_dir / f"{part_name}.png"

            # part_image_texture is BGR (from _extract_body_part from self.texture which is likely BGR)
            # _part_mask_roi_not_used is the alpha channel (from _extract_body_part)
            # We need to combine them into a BGRA image for saving with transparency.
            bgra_image_to_save = None
            if part_image_texture is not None and _part_mask_roi_not_used is not None:
                if part_image_texture.shape[:2] == _part_mask_roi_not_used.shape[:2]:
                    if part_image_texture.ndim == 2: # Grayscale texture
                        # Convert grayscale to BGR first then add alpha
                        bgr_texture = cv2.cvtColor(part_image_texture, cv2.COLOR_GRAY2BGR)
                        bgra_image_to_save = cv2.cvtColor(bgr_texture, cv2.COLOR_BGR2BGRA)
                    elif part_image_texture.shape[2] == 3: # BGR texture
                        bgra_image_to_save = cv2.cvtColor(part_image_texture, cv2.COLOR_BGR2BGRA)
                    elif part_image_texture.shape[2] == 4: # Already has alpha (e.g. RGBA or BGRA)
                        bgra_image_to_save = part_image_texture # Assume it's correctly formatted
                    else:
                        logging.error(f"Part '{part_name}' has unexpected texture channels: {part_image_texture.shape}")

                    if bgra_image_to_save is not None and bgra_image_to_save.shape[2] == 4:
                        bgra_image_to_save[:, :, 3] = _part_mask_roi_not_used # Apply/overwrite alpha channel
                    else:
                        logging.error(f"Failed to create BGRA image for part '{part_name}'. Texture shape: {part_image_texture.shape}")
                        bgra_image_to_save = None # Ensure it's None if conversion failed
                else:
                    logging.error(f"Shape mismatch between texture and alpha for part '{part_name}': {part_image_texture.shape[:2]} vs {_part_mask_roi_not_used.shape[:2]}")

            if bgra_image_to_save is not None:
                save_image(bgra_image_to_save, str(png_file_path))
            else:
                logging.error(f"Skipping PNG save for part '{part_name}' due to previous errors.")
                # Optionally, save the BGR part if alpha fails, or skip entirely
                # save_image(part_image_texture, str(png_file_path)) # Fallback to saving without alpha

            png_file_relative = f"{part_name}.png"

            # --- MODIFIED: Calculate local_pivot_offset based on anchor joint ---
            local_pivot_x = None
            local_pivot_y = None

            current_part_def_from_body_parts = BODY_PARTS.get(part_name, {})
            anchor_joint_id = current_part_def_from_body_parts.get("anchor_joint")

            if anchor_joint_id and self.texture_relative_joint_map and anchor_joint_id in self.texture_relative_joint_map:
                anchor_tex_x, anchor_tex_y = self.texture_relative_joint_map[anchor_joint_id]
                local_pivot_x = float(anchor_tex_x - roi_x)
                local_pivot_y = float(anchor_tex_y - roi_y)
                logging.debug(f"Part '{part_name}': Calculated local_pivot_offset [{local_pivot_x}, {local_pivot_y}] from anchor_joint '{anchor_joint_id}' ({anchor_tex_x}, {anchor_tex_y}) and ROI ({roi_x}, {roi_y}).")
            else:
                # Fallback to ROI center if anchor joint info is not available
                local_pivot_x = float(roi_w / 2)
                local_pivot_y = float(roi_h / 2)
                logging.warning(f"Part '{part_name}': Could not find anchor_joint '{anchor_joint_id}' in joint map or anchor_joint_id is not defined. Defaulting local_pivot_offset to ROI center [{local_pivot_x}, {local_pivot_y}].")
            # --- END MODIFICATION ---

            self.results['character']['parts'][part_name] = {
                "name": part_name,
                "roi": [float(roi_x), float(roi_y), float(roi_w), float(roi_h)],
                "image_path": str(png_file_path),
                "fill_color": current_part_def_from_body_parts.get('color', f"rgba({random.randint(0,255)},{random.randint(0,255)},{random.randint(0,255)},0.5)"),
                "local_pivot_offset": [float(local_pivot_x), float(local_pivot_y)],
                "z_value": float(current_part_def_from_body_parts.get("z_value", 0.0)),
                "fixed": bool(current_part_def_from_body_parts.get("fixed", False)),
                "anchor_joint_id": current_part_def_from_body_parts.get("anchor_joint") # ADDED anchor_joint_id
            }

            if self.generate_animations:
                proximal_joint_name = self._get_proximal_joint_name(part_name, current_part_def_from_body_parts)
                if proximal_joint_name and self.texture_relative_joint_map and proximal_joint_name in self.texture_relative_joint_map:
                    pivot_point = self.texture_relative_joint_map[proximal_joint_name]
                    local_pivot_for_anim = (pivot_point[0] - roi_x, pivot_point[1] - roi_y)

                    animation_frames = animate_body_part(part_image_texture, local_pivot_for_anim, num_frames=self.num_frames)
                    animation_output_path = self.output_dir / f"{part_name}_animation.gif"
                    save_animation(animation_frames, str(animation_output_path), fps=self.fps)
                    logging.info(f"Animation for {part_name} saved to {animation_output_path}")
                    self.results['character']['animations'][part_name] = {
                        'animation_path': str(animation_output_path),
                    }
                else:
                    logging.warning(f"Could not determine proximal joint or pivot for animation of {part_name}")

        self._generate_html_viewer()

        pydantic_skeleton_joints = []
        raw_skeleton_data_from_cfg = self.char_cfg.get('skeleton', []) if self.char_cfg else []

        raw_joint_map = {j_data.get("name"): j_data for j_data in raw_skeleton_data_from_cfg}

        for joint_data_from_cfg in raw_skeleton_data_from_cfg:
            joint_name = joint_data_from_cfg.get("name")
            if not joint_name:
                logging.warning(f"Skipping joint with no name in char_cfg: {joint_data_from_cfg}")
                continue

            loc = joint_data_from_cfg.get("loc", [0.0, 0.0])
            if not (isinstance(loc, list) and len(loc) == 2 and all(isinstance(p, (int, float)) for p in loc)):
                logging.warning(f"Invalid 'loc' for joint {joint_name}: {loc}. Defaulting to [0.0, 0.0].")
                loc = [0.0, 0.0]

            parent_name = joint_data_from_cfg.get("parent")

            pydantic_skeleton_joints.append({
                "id": joint_name,
                "name": joint_name,
                "position": [float(loc[0]), float(loc[1])],
                "parent": parent_name if parent_name in raw_joint_map else None
            })

        pydantic_parts = {}
        for part_name in self.results['character']['parts'].keys():
            original_part_dict = self.results['character']['parts'][part_name] # Get the dictionary populated in the earlier loop
            img_rel_path = Path(original_part_dict.get("image_path", "")).name if original_part_dict.get("image_path") else ""

            # Fetch definition from BODY_PARTS to get the authoritative anchor_joint
            current_part_def_from_body_parts = BODY_PARTS.get(part_name, {})

            pydantic_parts[part_name] = {
                "name": part_name,
                "roi": original_part_dict.get("roi"),
                "image_path": img_rel_path,
                "fill_color": original_part_dict.get("fill_color", 'rgba(128,128,128,0.5)'),
                "local_pivot_offset": original_part_dict.get("local_pivot_offset"),
                "z_value": float(original_part_dict.get("z_value", 0.0)),
                "fixed": bool(original_part_dict.get("fixed", False)),
                # Ensure anchor_joint_id is sourced from BODY_PARTS for the Pydantic model
                "anchor_joint_id": current_part_def_from_body_parts.get("anchor_joint")
            }

        character_name_from_cfg = self.char_cfg.get("name", self.char_dir.name) if self.char_cfg else self.char_dir.name

        output_data_for_pydantic_json = {
            "character": {
                "name": character_name_from_cfg,
                "parts": pydantic_parts,
                "skeleton_joints": pydantic_skeleton_joints
            }
        }

        parts_info_filepath = self.output_dir / "parts_info.json"
        try:
            with open(parts_info_filepath, 'w') as f:
                json.dump(output_data_for_pydantic_json, f, indent=4)
            logging.info(f"Pydantic-compatible parts_info.json saved to {parts_info_filepath}")
        except Exception as e:
            logging.error(f"Failed to save Pydantic-compatible parts_info.json: {e}", exc_info=True)

        logging.info(f"All body parts processed. Output directory: {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Extracts and processes character body parts.')
    parser.add_argument('char_dir', help='Character directory path')
    parser.add_argument('--output', '-o', default=None, help='Output directory path')
    parser.add_argument('--no-animation', action='store_true', help='Disable animation generation')
    parser.add_argument('--frames', '-f', type=int, default=30, help='Frames between keyframes for animation')
    parser.add_argument('--fps', type=int, default=24, help='Animation FPS')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    extractor = BodyPartsExtractor(
        char_dir=args.char_dir,
        output_dir=args.output,
        generate_animations=not args.no_animation,
        num_frames=args.frames,
        fps=args.fps
    )
    extractor.process()

if __name__ == "__main__":
    main()

# 사용 예제:
# 1. 신체 부위 분할 및 자동 애니메이션 생성:
#    python -m automataii.animate.body_parts_extractor /path/to/character
#
# 2. 신체 부위 분할만 수행 (애니메이션 생성 없음):
#    python -m automataii.animate.body_parts_extractor /path/to/character --no-animation
#
# 3. 사용자 정의 애니메이션 설정으로 실행:
#    python -m automataii.animate.body_parts_extractor /path/to/character --frames 60 --fps 30
#
# 애니메이션은 ARAP(As-Rigid-As-Possible) 알고리즘을 사용하여 자동 생성됩니다.
# 이 알고리즘은 메쉬를 변형할 때 지역적 강성을 유지하면서 자연스러운 변형을 제공합니다.
# 각 신체 부위는 BODY_PARTS 정의에 따라 자동으로 애니메이션 제어점과 키프레임이 생성됩니다.
