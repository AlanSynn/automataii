#!/usr/bin/env python

from typing import Optional
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

# SVG 템플릿 문자열
SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <path d="{path_data}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />
</svg>
"""

# HTML 뷰어 템플릿
HTML_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>신체 부위 뷰어</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .orig-image {{
            max-width: 100%;
            margin-bottom: 20px;
        }}
        .segmentation {{
            max-width: 100%;
            margin-bottom: 20px;
        }}
        .part-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            width: 300px;
        }}
        .part-card h3 {{
            margin-top: 0;
            color: #333;
        }}
        .part-image {{
            max-width: 100%;
            height: auto;
            display: block;
            margin-bottom: 10px;
        }}
        .part-svg {{
            max-width: 100%;
            height: auto;
            display: block;
            margin-bottom: 10px;
            background-color: #f0f0f0;
        }}
        .animation-container {{
            margin-top: 15px;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }}
        .animation-container h4 {{
            margin-top: 0;
            color: #555;
        }}
        .part-animation {{
            max-width: 100%;
            height: auto;
            display: block;
            border: 1px dashed #ccc;
            background-color: #f9f9f9;
        }}
        }}
        .tabs {{
            display: flex;
            margin-bottom: 10px;
        }}
        .tab {{
            padding: 8px 16px;
            background-color: #e0e0e0;
            border: none;
            cursor: pointer;
            margin-right: 5px;
            border-radius: 4px 4px 0 0;
        }}
        .tab.active {{
            background-color: #007bff;
            color: white;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <h1>캐릭터 신체 부위 분할 결과</h1>

    <div class="tabs">
        <button class="tab active" onclick="openTab('preview')">미리보기</button>
        <button class="tab" onclick="openTab('parts')">신체 부위</button>
    </div>

    <div id="preview" class="tab-content active">
        <h2>원본 이미지와 분할 결과</h2>
        <img src="{texture_path}" alt="원본 이미지" class="orig-image">
        <img src="{segmentation_path}" alt="분할 결과" class="segmentation">
    </div>

    <div id="parts" class="tab-content">
        <h2>신체 부위 목록</h2>
        <div class="container">
            {part_cards}
        </div>
    </div>

    <script>
        function openTab(tabName) {{
            // Hide all tab contents
            const tabContents = document.getElementsByClassName('tab-content');
            for (let i = 0; i < tabContents.length; i++) {{
                tabContents[i].classList.remove('active');
            }}

            // Deactivate all tabs
            const tabs = document.getElementsByClassName('tab');
            for (let i = 0; i < tabs.length; i++) {{
                tabs[i].classList.remove('active');
            }}

            // Show the selected tab content
            document.getElementById(tabName).classList.add('active');

            // Activate the clicked tab
            event.currentTarget.classList.add('active');
        }}
    </script>
</body>
</html>
"""

# 신체 부위 카드 템플릿
PART_CARD_TEMPLATE = """
<div class="part-card">
    <h3>{part_name}</h3>
    <img src="{image_path}" alt="{part_name}" class="part-image">
    <img src="{svg_path}" alt="{part_name} SVG" class="part-svg">
    {animation_element}
</div>
"""

# 몸 부위 정의
BODY_PARTS = {
    'head': {
        'joints': ['neck'],
        'is_extremity': True,
        'color': 'rgba(255,0,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'neck'},
                {'position': [0, -50]}  # Control point at top of head
            ]
        }
    },
    'torso': {
        'joints': ['torso', 'hip', 'left_shoulder', 'right_shoulder'],
        'is_extremity': False,
        'color': 'rgba(0,255,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'torso'},
                {'joint': 'hip'},
                {'joint': 'left_shoulder'},
                {'joint': 'right_shoulder'}
            ]
        }
    },
    'left_arm_upper': {
        'joints': ['left_shoulder', 'left_elbow'],
        'is_extremity': False,
        'color': 'rgba(0,0,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_shoulder'},
                {'joint': 'left_elbow'}
            ]
        }
    },
    'left_arm_lower': {
        'joints': ['left_elbow', 'left_hand'],
        'is_extremity': True,
        'color': 'rgba(255,255,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_elbow'},
                {'joint': 'left_hand'}
            ]
        }
    },
    'right_arm_upper': {
        'joints': ['right_shoulder', 'right_elbow'],
        'is_extremity': False,
        'color': 'rgba(255,0,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_shoulder'},
                {'joint': 'right_elbow'}
            ]
        }
    },
    'right_arm_lower': {
        'joints': ['right_elbow', 'right_hand'],
        'is_extremity': True,
        'color': 'rgba(0,255,255,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_elbow'},
                {'joint': 'right_hand'}
            ]
        }
    },
    'left_leg_upper': {
        'joints': ['left_hip', 'left_knee'],
        'is_extremity': False,
        'color': 'rgba(128,0,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_hip'},
                {'joint': 'left_knee'}
            ]
        }
    },
    'left_leg_lower': {
        'joints': ['left_knee', 'left_foot'],
        'is_extremity': True,
        'color': 'rgba(0,128,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'left_knee'},
                {'joint': 'left_foot'}
            ]
        }
    },
    'right_leg_upper': {
        'joints': ['right_hip', 'right_knee'],
        'is_extremity': False,
        'color': 'rgba(0,0,128,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_hip'},
                {'joint': 'right_knee'}
            ]
        }
    },
    'right_leg_lower': {
        'joints': ['right_knee', 'right_foot'],
        'is_extremity': True,
        'color': 'rgba(128,128,0,0.5)',
        'animation_controls': {
            'control_points': [
                {'joint': 'right_knee'},
                {'joint': 'right_foot'}
            ]
        }
    },
}

# NumPy 타입을 JSON으로 직렬화 가능하게 변환하는 클래스
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def read_char_config(config_path):
    """캐릭터 설정 파일을 읽어옵니다"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def create_joint_map(skeleton):
    """관절 이름과 위치를 매핑합니다"""
    joint_map = {}
    for joint in skeleton:
        joint_map[joint['name']] = tuple(joint['loc'])
    return joint_map

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

# This function has been moved to body_parts_animation.py

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

        # ARAP을 사용하여 마스크 개선 (제어 관절이 있는 경우)
        # try:
        #     # 부위별로 다른 확장 계수 적용
        #     expansion_factor = 1.5  # 기본값
        #     if 'head' in part_name:
        #         expansion_factor = 2.5  # 머리는 특별히 훨씬 더 크게 확장
        #     elif any(term in part_name for term in ['hand', 'foot']):
        #         expansion_factor = 1.8  # 팔다리 끝은 더 크게 확장
        #     elif any(term in part_name for term in ['torso']):
        #         expansion_factor = 1.3  # 몸통은 적당히 확장

        #     initial_mask = refine_mask_with_arap(initial_mask, joint_map, part_def['joints'], expansion_factor, part_name)
        # except Exception as e:
        #     logging.warning(f"부위 {part_name}의 ARAP 개선 실패: {e}")

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
        # try:
        #     # 부위별로 다른 확장 계수 적용
        #     expansion_factor = 1.1  # 기본값 (약간 확장)
        #     if 'head' in part_name:
        #         expansion_factor = 2.0  # 머리는 특별히 훨씬 더 크게 확장
        #     elif any(term in part_name for term in ['hand', 'foot']):
        #         expansion_factor = 1.3  # 팔다리 끝은 더 크게 확장
        #     elif any(term in part_name for term in ['arm', 'leg']):
        #         expansion_factor = 1.2  # 팔다리는 중간 정도 확장

        #     part_mask = refine_mask_with_arap(part_mask, joint_map, parts_def[part_name]['joints'],
        #                                     expansion_factor=expansion_factor, part_name=part_name)

        #     # 추가 팽창으로 경계 부드럽게 처리
        #     kernel = np.ones((3, 3), np.uint8)
        #     part_mask = cv2.dilate(part_mask, kernel, iterations=1)
        # except Exception as e:
        #     logging.warning(f"최종 마스크 {part_name}의 ARAP 개선 실패: {e}")

        # 작은 홀 다시 채우기
        kernel = np.ones((7, 7), np.uint8)
        part_mask = cv2.morphologyEx(part_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 캐릭터 마스크와 다시 교차 (확장된 부분이 캐릭터를 벗어나지 않도록)
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

def _get_proximal_joint_name(part_name: str, part_definition: dict) -> Optional[str]:
    """Determines the proximal joint name for a given part.
    Assumes the first joint listed in the part_definition['joints'] is proximal.
    For 'head', it's 'neck'. Torso might not have a single one, returns None.
    """
    if part_name == 'head':
        return 'neck'
    if part_name == 'torso':
        return None # Torso is the base, or its pivot is handled differently

    joints = part_definition.get('joints')
    if joints and isinstance(joints, list) and len(joints) > 0:
        # For parts like 'left_arm_upper' (joints: ['left_shoulder', 'left_elbow']),
        # the first one is proximal.
        return joints[0]
    return None

def extract_body_part(image, part_mask):
    """마스크를 사용하여 신체 부위 이미지를 추출합니다"""
    # 마스크의 경계 상자 계산
    indices = np.where(part_mask > 0)
    if len(indices[0]) == 0:  # 빈 마스크인 경우
        return None, None, None

    y_min, y_max = np.min(indices[0]), np.max(indices[0])
    x_min, x_max = np.min(indices[1]), np.max(indices[1])

    # ROI 계산 (int 타입으로 변환하여 JSON 직렬화 가능하게)
    roi = (int(x_min), int(y_min), int(x_max), int(y_max))

    # 이미지가 RGBA 형식인지 확인하고, 아니면 변환
    if image.shape[2] == 3:
        image_rgba = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    else:
        image_rgba = image.copy()

    # 알파 채널에 마스크 적용
    image_rgba[:, :, 3] = cv2.bitwise_and(image_rgba[:, :, 3] if image_rgba.shape[2] > 3 else 255, part_mask)

    # ROI 영역만 추출
    part_image = image_rgba[y_min:y_max+1, x_min:x_max+1].copy()
    part_mask_roi = part_mask[y_min:y_max+1, x_min:x_max+1].copy()

    return part_image, part_mask_roi, roi

def create_contour_from_mask(mask):
    """마스크에서 윤곽선을 추출합니다"""
    # 미세한 노이즈 제거 및 내부 홀 채우기 시도
    kernel = np.ones((5, 5), np.uint8) # 커널 크기 약간 증가
    # 열림 연산으로 작은 돌출부 제거
    # mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    # 닫힘 연산으로 작은 구멍 메우기
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3) # 반복 횟수 증가

    # 윤곽선 찾기 (닫힌 마스크에서)
    contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 가장 큰 윤곽선 찾기
    if contours:
        max_contour = max(contours, key=cv2.contourArea)
        # 윤곽선 근사화 추가 (CharacterPartItem과 유사하게)
        epsilon = 0.005 * cv2.arcLength(max_contour, True)
        approx_contour = cv2.approxPolyDP(max_contour, epsilon, True)
        return approx_contour

    return None

def contour_to_svg_path(contour):
    """윤곽선을 SVG 경로 데이터로 변환합니다"""
    if contour is None or len(contour) < 3:
        return ""

    # 윤곽선의 각 점을 SVG 경로 명령으로 변환
    points = contour.reshape(-1, 2)

    # 경로 시작
    path_data = f"M {points[0][0]},{points[0][1]} "

    # 나머지 점들을 선형 경로로 추가
    for point in points[1:]:
        path_data += f"L {point[0]},{point[1]} "

    # 경로 닫기
    path_data += "Z"

    return path_data

def save_svg(path_data, width, height, output_path, fill="rgba(255,255,255,0.5)", stroke="black", stroke_width=1):
    """SVG 파일을 저장합니다"""
    svg_content = SVG_TEMPLATE.format(
        width=width,
        height=height,
        path_data=path_data,
        fill_color=fill,
        stroke_color=stroke,
        stroke_width=stroke_width
    )

    with open(output_path, 'w') as f:
        f.write(svg_content)

def save_part_image(image, output_path):
    """분리된 신체 부위 이미지를 저장합니다"""
    if image is not None:
        cv2.imwrite(output_path, image)
        return True
    return False

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

def generate_html_viewer(results, output_dir, char_dir):
    """HTML 뷰어를 생성합니다"""
    part_cards = ""

    # 각 부위별 카드 생성
    for part_name, part_info in results['character']['parts'].items():
        image_path = os.path.basename(part_info['image_path'])
        svg_path = os.path.basename(part_info['svg_path'])

        # 애니메이션 요소 확인
        animation_element = ""
        if 'animations' in results['character'] and part_name in results['character']['animations']:
            animation_path = os.path.basename(results['character']['animations'][part_name]['animation_path'])
            animation_element = f'<div class="animation-container"><h4>Animation</h4><img src="{animation_path}" alt="{part_name} Animation" class="part-animation"></div>'

        part_card = PART_CARD_TEMPLATE.format(
            part_name=part_name.replace('_', ' ').title(),
            image_path=image_path,
            svg_path=svg_path,
            animation_element=animation_element
        )
        part_cards += part_card

    # 원본 이미지와 분할 결과 이미지 경로
    texture_path = os.path.relpath(os.path.join(char_dir, 'image.png'), output_dir)
    segmentation_path = "segmentation_vis.png"

    # HTML 생성
    html_content = HTML_VIEWER_TEMPLATE.format(
        texture_path=texture_path,
        segmentation_path=segmentation_path,
        part_cards=part_cards
    )

    # HTML 파일 저장
    html_output_path = os.path.join(output_dir, 'viewer.html')
    with open(html_output_path, 'w') as f:
        f.write(html_content)

    return html_output_path

def process_character(char_dir, output_dir, generate_animations=False, num_frames=30, fps=24):
    """캐릭터의 신체 부위를 처리하고 선택적으로 애니메이션을 생성합니다"""
    # 필요한 파일들의 경로
    char_cfg_path = os.path.join(char_dir, 'char_cfg.yaml')
    texture_path = os.path.join(char_dir, 'texture.png')
    mask_path = os.path.join(char_dir, 'mask.png')

    # 파일이 존재하는지 확인
    if not os.path.exists(char_cfg_path) or not os.path.exists(texture_path) or not os.path.exists(mask_path):
        print(f"필요한 파일을 찾을 수 없습니다: {char_dir}")
        return

    # 입력 디렉토리가 출력 디렉토리 내에 있는지 확인하여 중첩 디렉토리 생성 방지
    char_dir_abs = os.path.abspath(char_dir)
    output_dir_abs = os.path.abspath(output_dir)

    if output_dir_abs.startswith(char_dir_abs + os.sep):
        print(f"경고: 출력 디렉토리가 입력 디렉토리 내에 있습니다. 중첩 폴더 생성을 방지하기 위해 출력 경로를 조정합니다.")
        output_dir_abs = os.path.join(os.path.dirname(char_dir_abs), os.path.basename(output_dir_abs))
        output_dir = output_dir_abs

    # 설정 및 이미지 로드
    char_cfg = read_char_config(char_cfg_path)
    texture = cv2.imread(texture_path, cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    # 이미지 크기
    height, width = char_cfg['height'], char_cfg['width']

    # 관절 위치 매핑
    original_joint_map = create_joint_map(char_cfg['skeleton'])
    logging.debug(f"Original joint map from char_cfg: {original_joint_map}")

    # Bounding box 오프셋 읽기
    offset_x, offset_y = 0, 0
    bounding_box_path = Path(char_dir) / 'bounding_box.yaml'
    if bounding_box_path.exists():
        try:
            with open(bounding_box_path, 'r') as f:
                bbox_data = yaml.safe_load(f)
            if isinstance(bbox_data, dict) and 'left' in bbox_data and 'top' in bbox_data:
                offset_x = bbox_data['left']
                offset_y = bbox_data['top']
                logging.info(f"Loaded bounding box offset: left={offset_x}, top={offset_y}")
            else:
                logging.warning(f"Invalid bounding_box.yaml format in {bounding_box_path}. Using (0,0) offset.")
        except Exception as e:
            logging.warning(f"Error loading bounding_box.yaml from {bounding_box_path}: {e}. Using (0,0) offset.")
    else:
        logging.info(f"bounding_box.yaml not found in {char_dir}. Assuming (0,0) offset for joints relative to texture.png.")

    # 텍스처 이미지에 상대적인 관절 위치로 조정
    texture_relative_joint_map = {}
    for name, loc in original_joint_map.items():
        adj_x = int(loc[0] - offset_x)
        adj_y = int(loc[1] - offset_y)
        texture_relative_joint_map[name] = (adj_x, adj_y)
    logging.debug(f"Texture-relative joint map: {texture_relative_joint_map}")

    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)

    # 신체 부위 분할 (ARAP 알고리즘으로 개선된 방식 사용)
    part_masks = segment_body_parts(texture, mask, texture_relative_joint_map, BODY_PARTS)

    # 분할 결과 시각화
    visualize_segmentation(mask, part_masks, texture_relative_joint_map, os.path.join(output_dir, 'segmentation_vis.png'))

    # 결과 저장을 위한 정보
    results = {
        'character': {
            'width': int(width),
            'height': int(height),
            'parts': {},
            'joint_map': texture_relative_joint_map,
            'skeleton': char_cfg['skeleton'],
            'animations': {}
        }
    }

    # 각 신체 부위 처리
    for part_name, part_mask in part_masks.items():
        print(f"처리 중: {part_name}")

        # 신체 부위 추출
        part_image, part_mask_roi, roi = extract_body_part(texture, part_mask)

        if part_image is None:
            print(f"부위를 추출할 수 없습니다: {part_name}")
            continue

        # 마스킹된 이미지 저장
        part_output_path = os.path.join(output_dir, f"{part_name}.png")
        if save_part_image(part_image, part_output_path):
            # 윤곽선 추출
            contour = create_contour_from_mask(part_mask)

            if contour is None or len(contour) < 3:
                print(f"윤곽선을 추출할 수 없습니다: {part_name}")
                continue

            # SVG 경로 데이터 생성
            path_data = contour_to_svg_path(contour)

            if not path_data:
                print(f"SVG 경로 데이터를 생성할 수 없습니다: {part_name}")
                continue

            # SVG 색상 설정 (정의된 색상 사용 또는 임의의 반투명 색상)
            fill_color = BODY_PARTS[part_name].get('color', f"rgba({random.randint(0, 255)},{random.randint(0, 255)},{random.randint(0, 255)},0.5)")

            # SVG 저장
            svg_output_path = os.path.join(output_dir, f"{part_name}.svg")
            save_svg(path_data, width, height, svg_output_path, fill=fill_color)

            # SVG 파일이 생성되었는지 확인
            if not os.path.exists(svg_output_path):
                print(f"SVG 파일 생성 실패: {svg_output_path}")
            else:
                print(f"SVG 파일 생성 성공: {svg_output_path}")

            # --- Calculate and store local_pivot_offset ---
            local_pivot_offset = [0,0] # Default for torso or if not found
            current_part_def = BODY_PARTS.get(part_name)
            if current_part_def:
                proximal_joint_name = _get_proximal_joint_name(part_name, current_part_def)
                if proximal_joint_name and proximal_joint_name in texture_relative_joint_map:
                    global_proximal_x, global_proximal_y = texture_relative_joint_map[proximal_joint_name]
                    # roi is (x_min_texture, y_min_texture, x_max_texture, y_max_texture)
                    local_pivot_x = global_proximal_x - roi[0]
                    local_pivot_y = global_proximal_y - roi[1]
                    local_pivot_offset = [local_pivot_x, local_pivot_y]
                    logging.info(f"Part '{part_name}': Proximal joint '{proximal_joint_name}' at global ({global_proximal_x},{global_proximal_y}), ROI_xmin={roi[0]}, ROI_ymin={roi[1]}. Calculated local_pivot_offset: {local_pivot_offset}")
                elif proximal_joint_name:
                    logging.warning(f"Part '{part_name}': Proximal joint '{proximal_joint_name}' defined but not found in texture_relative_joint_map. Using default pivot [0,0].")
            # --- End local_pivot_offset calculation ---

            # 결과 정보 저장
            results['character']['parts'][part_name] = {
                'roi': roi,
                'svg_path': svg_output_path,
                'image_path': part_output_path,
                'fill_color': fill_color,
                'local_pivot_offset': local_pivot_offset # Add the new offset
            }

            # 애니메이션 생성 (선택적)
            if generate_animations and part_name in BODY_PARTS and 'animation_controls' in BODY_PARTS[part_name]:
                print(f"애니메이션 생성 중: {part_name}")

                # 부위별 애니메이션 설정 가져오기
                animation_config = BODY_PARTS[part_name].get('animation_controls', {})

                # 제어점 생성 (관절 위치 기반)
                control_points = []
                for control_def in animation_config.get('control_points', []):
                    if 'joint' in control_def:
                        # 관절 위치를 기준으로 제어점 설정
                        joint_name = control_def['joint']
                        if joint_name in texture_relative_joint_map:
                            # 글로벌 좌표를 로컬 좌표로 변환 (ROI 기준)
                            x, y = texture_relative_joint_map[joint_name]
                            local_x = x - roi[0]
                            local_y = y - roi[1]
                            control_points.append((local_x, local_y))
                    elif 'position' in control_def:
                        # 직접 좌표 지정
                        x, y = control_def['position']
                        # 글로벌 좌표를 로컬 좌표로 변환 (ROI 기준)
                        local_x = x - roi[0]
                        local_y = y - roi[1]
                        control_points.append((local_x, local_y))

                if not control_points:
                    # 제어점이 없으면 윤곽선에서 샘플링
                    contour_points = np.array(contour).reshape(-1, 2)
                    # 윤곽선에서 균등하게 4개 점 선택
                    step = len(contour_points) // 4
                    for i in range(0, len(contour_points), step):
                        if len(control_points) >= 4:
                            break
                        x, y = contour_points[i]
                        # 글로벌 좌표를 로컬 좌표로 변환 (ROI 기준)
                        local_x = x - roi[0]
                        local_y = y - roi[1]
                        control_points.append((local_x, local_y))

                # 기본 키프레임 생성 (없을 경우)
                keyframes = animation_config.get('keyframes', [])
                if not keyframes:
                    # 기본 키프레임: 원본 위치, 약간 회전, 원본 위치
                    keyframes = [
                        # 키프레임 1: 원본 위치
                        control_points.copy(),

                        # 키프레임 2: 시계 방향 회전 (10도)
                        [],

                        # 키프레임 3: 다시 원본 위치
                        control_points.copy()
                    ]

                    # 키프레임 2를 계산 (10도 회전)
                    center_x = sum(p[0] for p in control_points) / len(control_points)
                    center_y = sum(p[1] for p in control_points) / len(control_points)
                    angle_rad = np.radians(10)
                    cos_val = np.cos(angle_rad)
                    sin_val = np.sin(angle_rad)

                    for x, y in control_points:
                        # 중심점 기준으로 회전
                        dx = x - center_x
                        dy = y - center_y
                        rotated_x = center_x + dx * cos_val - dy * sin_val
                        rotated_y = center_y + dx * sin_val + dy * cos_val
                        keyframes[1].append((rotated_x, rotated_y))

                try:
                    # 애니메이션 생성
                    animation_frames = animate_body_part(part_image, part_mask_roi, control_points, keyframes, num_frames)

                    # GIF 파일로 저장
                    animation_output_path = os.path.join(output_dir, f"{part_name}_animation.gif")
                    if save_animation(animation_frames, animation_output_path, fps):
                        print(f"애니메이션 저장 완료: {animation_output_path}")

                        # 애니메이션 정보 저장
                        results['character']['animations'][part_name] = {
                            'animation_path': animation_output_path,
                            'control_points': control_points,
                            'keyframes': keyframes,
                            'frames': num_frames,
                            'fps': fps
                        }
                except Exception as e:
                    print(f"{part_name} 애니메이션 생성 중 오류 발생: {e}")
        else:
            print(f"이미지를 저장할 수 없습니다: {part_name}")

    # 결과 정보를 JSON으로 저장 (NumPy 타입 처리를 위한 인코더 사용)
    with open(os.path.join(output_dir, 'parts_info.json'), 'w') as f:
        json.dump(results, f, indent=2, cls=NumpyEncoder)

    # HTML 뷰어 생성
    html_path = generate_html_viewer(results, output_dir, char_dir)
    print(f"HTML 뷰어 생성 완료: {html_path}")

    print(f"모든 신체 부위 처리 완료. 출력 디렉토리: {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='캐릭터의 신체 부위를 분리하고 SVG로 변환합니다.')
    parser.add_argument('char_dir', help='캐릭터 디렉토리 경로')
    parser.add_argument('--output', '-o', default=None, help='출력 디렉토리 경로 (기본값: 입력 디렉토리와 같은 수준의 body_parts_output)')
    parser.add_argument('--no-animation', action='store_true', help='애니메이션 생성을 비활성화합니다')
    parser.add_argument('--frames', '-f', type=int, default=30, help='애니메이션 키프레임 사이에 생성할 프레임 수 (기본값: 30)')
    parser.add_argument('--fps', type=int, default=24, help='애니메이션 FPS (기본값: 24)')

    args = parser.parse_args()

    # 기본 출력 디렉토리를 입력 디렉토리와 같은 레벨에 설정
    if args.output is None:
        parent_dir = os.path.dirname(os.path.abspath(args.char_dir))
        args.output = os.path.join(parent_dir, 'body_parts_output')

    print(f"입력 디렉토리: {args.char_dir}")
    print(f"출력 디렉토리: {args.output}")

    # 신체 부위 처리 (애니메이션 생성 포함)
    process_character(args.char_dir, args.output, not args.no_animation, args.frames, args.fps)

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
