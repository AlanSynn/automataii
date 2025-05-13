#!/usr/bin/env python

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
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
</div>
"""

# 몸 부위 정의
BODY_PARTS = {
    'head': {'joints': ['neck'], 'is_extremity': True, 'color': 'rgba(255,0,0,0.5)'},
    'torso': {'joints': ['torso', 'hip', 'left_shoulder', 'right_shoulder'], 'is_extremity': False, 'color': 'rgba(0,255,0,0.5)'},
    'left_arm_upper': {'joints': ['left_shoulder', 'left_elbow'], 'is_extremity': False, 'color': 'rgba(0,0,255,0.5)'},
    'left_arm_lower': {'joints': ['left_elbow', 'left_hand'], 'is_extremity': True, 'color': 'rgba(255,255,0,0.5)'},
    'right_arm_upper': {'joints': ['right_shoulder', 'right_elbow'], 'is_extremity': False, 'color': 'rgba(255,0,255,0.5)'},
    'right_arm_lower': {'joints': ['right_elbow', 'right_hand'], 'is_extremity': True, 'color': 'rgba(0,255,255,0.5)'},
    'left_leg_upper': {'joints': ['left_hip', 'left_knee'], 'is_extremity': False, 'color': 'rgba(128,0,0,0.5)'},
    'left_leg_lower': {'joints': ['left_knee', 'left_foot'], 'is_extremity': True, 'color': 'rgba(0,128,0,0.5)'},
    'right_leg_upper': {'joints': ['right_hip', 'right_knee'], 'is_extremity': False, 'color': 'rgba(0,0,128,0.5)'},
    'right_leg_lower': {'joints': ['right_knee', 'right_foot'], 'is_extremity': True, 'color': 'rgba(128,128,0,0.5)'},
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

    # 선 그리기 (굵은 선으로 관절 연결)
    cv2.line(bone_mask, start_pos, end_pos, 255, thickness)

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

def calculate_head_mask(joint_map, mask_shape, head_factor=1.5):
    """머리 영역의 마스크를 계산합니다"""
    if 'neck' not in joint_map or 'torso' not in joint_map:
        return None

    neck_pos = joint_map['neck']
    torso_pos = joint_map['torso']

    # 목과 몸통 사이의 거리 계산
    dx = neck_pos[0] - torso_pos[0]
    dy = neck_pos[1] - torso_pos[1]
    dist = np.sqrt(dx*dx + dy*dy)

    # 머리 중심 추정
    head_center_x = int(neck_pos[0])
    head_center_y = int(neck_pos[1] - dist * 0.5)

    # 머리 크기 추정
    head_radius = int(dist * head_factor)

    # 머리 마스크 생성
    head_mask = np.zeros(mask_shape, dtype=np.uint8)
    cv2.circle(head_mask, (head_center_x, head_center_y), head_radius, 255, -1)

    return head_mask

def create_part_mask(char_mask, joint_map, part_def, mask_shape):
    """신체 부위의 마스크를 생성합니다"""
    # 특별 케이스: 머리
    if 'head' in part_def:
        return calculate_head_mask(joint_map, mask_shape)

    # 관절 위치와 뼈대 마스크 생성
    joints = part_def['joints']
    part_mask = np.zeros(mask_shape, dtype=np.uint8)

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

        # 각 관절 쌍에 대해 뼈대 마스크 생성
        for start_joint, end_joint in pairs:
            bone_mask = create_bone_mask(joint_map, start_joint, end_joint, mask_shape)
            if bone_mask is not None:
                part_mask = cv2.bitwise_or(part_mask, bone_mask)
    else:
        # 기존 로직: 연속된 관절 연결
        for i in range(len(joints) - 1):
            bone_mask = create_bone_mask(joint_map, joints[i], joints[i+1], mask_shape)
            if bone_mask is not None:
                part_mask = cv2.bitwise_or(part_mask, bone_mask)

    # 추가적인 관절 영역
    for joint in joints:
        joint_mask = create_joint_mask(joint_map, joint, mask_shape)
        if joint_mask is not None:
            part_mask = cv2.bitwise_or(part_mask, joint_mask)

    # 팽창 연산으로 마스크 확장
    kernel = np.ones((5, 5), np.uint8)
    part_mask = cv2.dilate(part_mask, kernel, iterations=3)

    # 캐릭터 마스크와 교차하여 실제 영역만 가져오기
    part_mask = cv2.bitwise_and(part_mask, char_mask)

    return part_mask

def segment_body_parts(texture, character_mask, joint_map, parts_def):
    """전체 마스크를 신체 부위별로 분할합니다 (Watershed 사용)"""
    height, width = character_mask.shape
    mask_shape = (height, width)
    logging.info("Segmenting body parts using Watershed algorithm...")

    # 1. 각 부위별 초기 마스크 생성 (create_part_mask 사용)
    initial_part_masks = {}
    for part_name, part_def in parts_def.items():
        initial_mask = create_part_mask(character_mask, joint_map, part_def, mask_shape)
        if initial_mask is None:
            initial_mask = np.zeros(mask_shape, dtype=np.uint8)
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
            sure_fg = cv2.erode(initial_mask, kernel, iterations=2)

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
    #logging.debug(f"Marker unique values: {np.unique(markers)}")

    # 3. Watershed를 위한 이미지 준비 (마스크 사용으로 복귀)
    img_for_watershed = cv2.cvtColor(character_mask, cv2.COLOR_GRAY2BGR)
    logging.debug("Prepared 3-channel image for watershed from character mask (reverted).")

    # 4. Watershed 실행
    logging.info("Running Watershed...")
    cv2.watershed(img_for_watershed, markers)
    logging.info("Watershed complete.")

    # Watershed 결과에서 경계선(-1)이 생성될 수 있음
    # logging.debug(f"Watershed output unique values: {np.unique(markers)}")

    # 5. 최종 부위별 마스크 생성
    final_part_masks = {}
    for m_id, part_name in part_name_map.items():
        # Watershed 결과에서 해당 마커 ID를 가진 픽셀 선택
        part_mask = np.zeros(mask_shape, dtype=np.uint8)
        part_mask[markers == m_id] = 255

        # 원본 캐릭터 마스크와 교차하여 배경 픽셀 제거
        # (Watershed가 마스크 밖으로 확장될 수 있으므로 중요)
        part_mask = cv2.bitwise_and(part_mask, character_mask)

        # 추가적인 후처리: 작은 노이즈 제거 (Opening)
        # kernel_post = np.ones((3,3), np.uint8)
        # part_mask = cv2.morphologyEx(part_mask, cv2.MORPH_OPEN, kernel_post, iterations=1)

        final_part_masks[part_name] = part_mask
        logging.debug(f"Generated final mask for {part_name} with {np.count_nonzero(part_mask)} pixels")

    # 원래 parts_def에 없는 ID에 할당된 픽셀 처리 (예: 경계 -1)
    # 필요시 이 픽셀들을 가장 가까운 유효한 부분에 할당할 수 있음 (후처리)
    # 현재는 무시됨

    return final_part_masks

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

        part_card = PART_CARD_TEMPLATE.format(
            part_name=part_name.replace('_', ' ').title(),
            image_path=image_path,
            svg_path=svg_path
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

def process_character(char_dir, output_dir):
    """캐릭터의 신체 부위를 처리합니다"""
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
    joint_map = create_joint_map(char_cfg['skeleton'])

    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)

    # 신체 부위 분할 (텍스처 이미지 전달)
    part_masks = segment_body_parts(texture, mask, joint_map, BODY_PARTS)

    # 분할 결과 시각화
    visualize_segmentation(mask, part_masks, joint_map, os.path.join(output_dir, 'segmentation_vis.png'))

    # 결과 저장을 위한 정보
    results = {
        'character': {
            'width': int(width),
            'height': int(height),
            'parts': {},
            'joint_map': joint_map,
            'skeleton': char_cfg['skeleton']
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

            # 결과 정보 저장
            results['character']['parts'][part_name] = {
                'roi': roi,
                'svg_path': svg_output_path,
                'image_path': part_output_path,
                'fill_color': fill_color
            }
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

    args = parser.parse_args()

    # 기본 출력 디렉토리를 입력 디렉토리와 같은 레벨에 설정
    if args.output is None:
        parent_dir = os.path.dirname(os.path.abspath(args.char_dir))
        args.output = os.path.join(parent_dir, 'body_parts_output')

    print(f"입력 디렉토리: {args.char_dir}")
    print(f"출력 디렉토리: {args.output}")

    process_character(args.char_dir, args.output)

if __name__ == "__main__":
    main()