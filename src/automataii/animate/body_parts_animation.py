#!/usr/bin/env python

import cv2
import numpy as np
import os
import logging
from scipy.ndimage import distance_transform_edt
from .arap import ARAP

def deform_body_part(part_image, part_mask, control_points, target_points):
    """
    ARAP(As-Rigid-As-Possible) 알고리즘을 사용하여 신체 부위를 변형합니다.
    
    Args:
        part_image: 변형할 신체 부위 이미지 (RGBA)
        part_mask: 신체 부위 마스크
        control_points: 원본 제어점 좌표 [(x1, y1), (x2, y2), ...]
        target_points: 대상 제어점 좌표 [(x1', y1'), (x2', y2'), ...]
        
    Returns:
        deformed_image: 변형된 신체 부위 이미지
    """
    # 마스크가 없는 경우 원본 이미지 반환
    if part_mask is None or np.sum(part_mask) == 0:
        return part_image
    
    # 마스크 경계 윤곽선 추출
    contours, _ = cv2.findContours(part_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return part_image
    
    # 가장 큰 윤곽선 선택
    contour = max(contours, key=cv2.contourArea)
    
    # 윤곽선 점을 샘플링하여 메쉬 정점으로 사용
    points = []
    step = max(1, len(contour) // 100)  # 윤곽선 점 샘플링 간격
    for i in range(0, len(contour), step):
        x, y = contour[i][0]
        points.append((float(x), float(y)))
    
    # 제어점 추가
    for cp in control_points:
        points.append((float(cp[0]), float(cp[1])))
    
    # 모든 점을 포함하는 확장된 경계 사각형 계산
    all_points = np.array(points, dtype=np.float32)
    x_min, y_min = np.min(all_points, axis=0) - 10  # 여유 공간 추가
    x_max, y_max = np.max(all_points, axis=0) + 10
    
    # 확장된 사각형으로 Subdiv2D 초기화
    rect = (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))
    subdiv = cv2.Subdiv2D(rect)
    
    # 삼각분할을 위해 점들을 추가 (유효 범위 내의 점만)
    for point in points:
        # 유효 범위 확인 후 추가
        if (rect[0] < point[0] < rect[0] + rect[2] and 
            rect[1] < point[1] < rect[1] + rect[3]):
            try:
                subdiv.insert(point)
            except cv2.error:
                # 점 추가 오류 무시하고 계속 진행
                pass
    
    # 삼각형 목록 가져오기
    try:
        triangles = subdiv.getTriangleList()
    except cv2.error:
        # 삼각분할 실패시 원본 이미지 반환
        return part_image
    
    # 삼각형이 없으면 원본 이미지 반환
    if len(triangles) == 0:
        return part_image
        
    # 삼각형 리스트 변환
    triangle_indices = []
    vertices = np.array(points, dtype=np.float32)
    
    # 삼각형 꼭지점을 정점 인덱스로 변환
    for t in triangles:
        pt1 = (t[0], t[1])
        pt2 = (t[2], t[3])
        pt3 = (t[4], t[5])
        
        # 삼각형 꼭지점이 points 리스트에 있는지 확인
        idx1 = next((i for i, p in enumerate(points) if np.allclose(p, pt1, atol=1.0)), None)
        idx2 = next((i for i, p in enumerate(points) if np.allclose(p, pt2, atol=1.0)), None)
        idx3 = next((i for i, p in enumerate(points) if np.allclose(p, pt3, atol=1.0)), None)
        
        if idx1 is not None and idx2 is not None and idx3 is not None:
            triangle_indices.append(np.array([idx1, idx2, idx3], dtype=np.int32))
    
    # 삼각형이 충분하지 않으면 원본 이미지 반환
    if len(triangle_indices) < 3:
        return part_image
    
    # 제어점 인덱스 찾기
    control_indices = []
    for i, p in enumerate(points):
        for cp in control_points:
            if np.allclose(p, cp, atol=1.0):
                control_indices.append(i)
                break
    
    # 제어점 위치를 numpy 배열로 변환
    np_control_points = np.array(control_points, dtype=np.float32)
    np_target_points = np.array(target_points, dtype=np.float32)
    
    try:
        # ARAP 초기화 및 변형 계산
        arap = ARAP(np_control_points, triangle_indices, vertices)
        deformed_vertices = arap.solve(np_target_points)
    except Exception as e:
        # ARAP 계산 실패 시 원본 이미지 반환
        print(f"ARAP 변형 계산 실패: {e}")
        return part_image
    
    # 변형 맵 생성
    height, width = part_image.shape[:2]
    map_x = np.zeros((height, width), dtype=np.float32)
    map_y = np.zeros((height, width), dtype=np.float32)
    
    # 초기화: 기본값은 원래 위치
    for y in range(height):
        for x in range(width):
            map_x[y, x] = x
            map_y[y, x] = y
    
    try:
        # 각 삼각형에 대해 변형 맵 계산
        for triangle in triangle_indices:
            # 원본 및 변형된 삼각형 꼭지점
            src_tri = np.array([vertices[triangle[0]], vertices[triangle[1]], vertices[triangle[2]]], dtype=np.float32)
            dst_tri = np.array([deformed_vertices[triangle[0]], deformed_vertices[triangle[1]], deformed_vertices[triangle[2]]], dtype=np.float32)
            
            # 삼각형 영역 계산
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillConvexPoly(mask, np.int32(src_tri), 1)
            
            try:
                # 아핀 변환 행렬 계산
                warp_mat = cv2.getAffineTransform(src_tri, dst_tri)
                
                # 삼각형 내부의 모든 픽셀에 대해 매핑 계산
                for y in range(height):
                    for x in range(width):
                        if mask[y, x]:
                            # 아핀 변환 적용
                            dst_x = warp_mat[0, 0] * x + warp_mat[0, 1] * y + warp_mat[0, 2]
                            dst_y = warp_mat[1, 0] * x + warp_mat[1, 1] * y + warp_mat[1, 2]
                            map_x[y, x] = dst_x
                            map_y[y, x] = dst_y
            except cv2.error:
                # 아핀 변환 계산 실패 시 이 삼각형은 건너뜀
                continue
        
        # 변형 맵 적용
        deformed_image = cv2.remap(part_image, map_x, map_y, cv2.INTER_LINEAR)
        return deformed_image
    except Exception as e:
        print(f"변형 맵 계산 실패: {e}")
        return part_image

def animate_body_part(part_image, part_mask, control_points, animation_keyframes, num_frames=30):
    """
    신체 부위의 애니메이션 시퀀스를 생성합니다.
    
    Args:
        part_image: 변형할 신체 부위 이미지 (RGBA)
        part_mask: 신체 부위 마스크
        control_points: 원본 제어점 좌표 [(x1, y1), (x2, y2), ...]
        animation_keyframes: 키프레임별 제어점 좌표 리스트 [[(x1', y1'), ...], [(x1'', y1''), ...], ...]
        num_frames: 각 키프레임 사이에 생성할 프레임 수
        
    Returns:
        frames: 애니메이션 프레임 목록
    """
    frames = []
    keyframe_count = len(animation_keyframes)
    
    if keyframe_count < 2:
        print("애니메이션을 위해서는 최소 2개의 키프레임이 필요합니다.")
        return [part_image]
    
    # 각 키프레임 쌍에 대해 보간된 프레임 생성
    for i in range(keyframe_count - 1):
        start_keyframe = animation_keyframes[i]
        end_keyframe = animation_keyframes[i + 1]
        
        # 시작 프레임 추가
        if i == 0:
            try:
                frames.append(deform_body_part(part_image, part_mask, control_points, start_keyframe))
            except Exception as e:
                print(f"시작 프레임 생성 실패: {e}")
                frames.append(part_image)
        
        # 키프레임 사이의 보간된 프레임 생성
        for t in range(1, num_frames + 1):
            # 프레임 간 선형 보간 계수 (0.0 ~ 1.0)
            alpha = t / (num_frames + 1)
            
            # 제어점 위치 보간
            current_points = []
            for j in range(len(control_points)):
                start_x, start_y = start_keyframe[j]
                end_x, end_y = end_keyframe[j]
                
                # 선형 보간
                current_x = start_x + alpha * (end_x - start_x)
                current_y = start_y + alpha * (end_y - start_y)
                current_points.append((current_x, current_y))
            
            try:
                # ARAP 알고리즘을 사용하여 신체 부위 변형
                deformed_frame = deform_body_part(part_image, part_mask, control_points, current_points)
                frames.append(deformed_frame)
            except Exception as e:
                print(f"보간 프레임 생성 실패: {e}")
                frames.append(part_image)
        
        # 마지막 키프레임만 추가 (마지막 반복에서)
        if i == keyframe_count - 2:
            try:
                frames.append(deform_body_part(part_image, part_mask, control_points, end_keyframe))
            except Exception as e:
                print(f"마지막 프레임 생성 실패: {e}")
                frames.append(part_image)
    
    return frames

def save_animation(frames, output_path, fps=24):
    """
    애니메이션 프레임을 GIF 또는 비디오 파일로 저장합니다.
    
    Args:
        frames: 애니메이션 프레임 목록
        output_path: 출력 파일 경로 (.gif 또는 .mp4)
        fps: 초당 프레임 수
    """
    if not frames:
        print("저장할 프레임이 없습니다.")
        return False
    
    if output_path.endswith('.gif'):
        # GIF로 저장
        import imageio
        
        # RGBA에서 RGB로 변환 (알파 채널 적용)
        rgb_frames = []
        for frame in frames:
            # 흰색 배경에 알파 채널 적용
            if frame.shape[2] == 4:
                # 알파 채널이 있는 경우
                alpha = frame[:, :, 3:4] / 255.0
                rgb = frame[:, :, :3] * alpha + (1 - alpha) * 255
                rgb_frames.append(rgb.astype(np.uint8))
            else:
                rgb_frames.append(frame[:, :, :3])
        
        imageio.mimsave(output_path, rgb_frames, fps=fps)
        print(f"GIF 저장 완료: {output_path}")
        return True
    
    elif output_path.endswith('.mp4'):
        # MP4로 저장
        height, width = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for frame in frames:
            # RGBA에서 BGR로 변환 (OpenCV 형식)
            if frame.shape[2] == 4:
                # 흰색 배경에 알파 채널 적용
                alpha = frame[:, :, 3:4] / 255.0
                rgb = frame[:, :, :3] * alpha + (1 - alpha) * 255
                bgr = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
                video.write(bgr)
            else:
                video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        
        video.release()
        print(f"비디오 저장 완료: {output_path}")
        return True
    
    else:
        print(f"지원되지 않는 파일 형식: {output_path}")
        return False

def refine_mask_with_arap(mask, joint_map, control_joints, expansion_factor=1.5, part_name=None):
    """ARAP 알고리즘을 사용하여 마스크를 확장 및 개선합니다"""
    # 머리 영역인지 확인 (확장 및 정확성을 위해 중요)
    is_head = part_name == 'head' or any(joint for joint in control_joints if 'head' in joint or 'neck' in joint)
    # 마스크가 너무 작으면 먼저 확장
    if np.sum(mask) < 100:
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)

    # 마스크의 윤곽선 추출 (모든 윤곽선 가져오기)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return mask
    
    # 가장 큰 윤곽선 선택
    contour = max(contours, key=cv2.contourArea)
    
    # 더 세밀한 윤곽선을 위해 근사화 조정
    epsilon = 0.003 * cv2.arcLength(contour, True)  # 더 작은 값으로 조정하여 더 세밀하게
    approx_contour = cv2.approxPolyDP(contour, epsilon, True)
    
    # 더 많은 윤곽선 점 샘플링 (기존 20개에서 40개로 증가)
    points = []
    step = max(1, len(approx_contour) // 40)
    for i in range(0, len(approx_contour), step):
        points.append(approx_contour[i][0].astype(float))
    
    # 마스크가 너무 단순하면 추가 점 생성
    if len(points) < 10:
        # 더 촘촘한 간격으로 재샘플링
        refined_points = []
        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i+1]
            refined_points.append(p1)
            # 중간점 추가
            for j in range(1, 4):
                t = j / 4
                mid_point = p1 * (1-t) + p2 * t
                refined_points.append(mid_point)
        refined_points.append(points[-1])
        points = refined_points
    
    # 제어점 (관절 위치) - 모든 제어점을 마스크 내부에 있는지 확인
    control_points = []
    mask_indices = np.where(mask > 0)
    mask_points = set(zip(mask_indices[1], mask_indices[0]))  # x, y 좌표 쌍
    
    for joint_name in control_joints:
        if joint_name in joint_map:
            joint_pos = np.array(joint_map[joint_name], dtype=float)
            x, y = int(joint_pos[0]), int(joint_pos[1])
            
            # 관절이 마스크 내부에 있는지 확인하거나 가장 가까운 마스크 점 찾기
            if (x, y) in mask_points:
                control_points.append(joint_pos)
            else:
                # 마스크 내부의 가장 가까운 점 찾기
                min_dist = float('inf')
                closest_point = None
                
                for mx, my in mask_points:
                    dist = np.sqrt((x - mx)**2 + (y - my)**2)
                    if dist < min_dist:
                        min_dist = dist
                        closest_point = np.array([float(mx), float(my)])
                
                if closest_point is not None and min_dist < 50:  # 50픽셀 이내에 있으면 사용
                    control_points.append(closest_point)
    
    # 제어점이 없으면 원래 마스크 반환
    if not control_points:
        # 대안으로 윤곽선의 특징점을 제어점으로 사용
        if len(points) >= 4:
            # 4개의 특징점 선택 (대략 사각형 모서리 위치)
            indices = np.linspace(0, len(points)-1, 4, dtype=int)
            control_points = [points[i] for i in indices]
        else:
            return mask
    
    # 윤곽선 확장을 위한 타겟 포인트 계산 (확장 방향 최적화)
    target_points = []
    center = np.mean(points, axis=0)
        
    # 머리 영역일 경우 확장 계수 증가
    head_expansion_factor = 1.8 if is_head else 1.0
        
    for cp in control_points:
        # 중심점에서 바깥쪽으로 확장
        direction = cp - center
            
        # 확장 벡터 계산 (길이에 따라 다른 확장 계수 적용)
        norm = np.linalg.norm(direction)
        if norm > 0:
            # 관절 위치에 따라 다른 확장 계수 적용
            # 끝 부분 관절(팔, 다리 끝)은 더 많이 확장
            joint_name = None
            for jname in control_joints:
                if jname in joint_map and np.allclose(cp, joint_map[jname], atol=5.0):
                    joint_name = jname
                    break
                        
            local_expansion = expansion_factor * head_expansion_factor
            if joint_name and any(term in joint_name for term in ['hand', 'foot']):
                local_expansion = expansion_factor * 1.3  # 끝 부분은 30% 더 확장
            elif joint_name and any(term in joint_name for term in ['head', 'neck']):
                local_expansion = expansion_factor * 2.0  # 머리는 100% 더 확장
            
            direction = direction / norm * local_expansion
            # 마스크 경계 근처에서는 더 많이 확장
            edge_dist = min([np.linalg.norm(cp - p) for p in points])
            if edge_dist < 20:  # 경계 근처
                direction *= 1.2
                
            target_points.append(cp + direction)
        else:
            target_points.append(cp)
    
    try:
        # ARAP으로 변형된 윤곽선 계산
        height, width = mask.shape
        
        # 삼각형 메쉬 생성 (확장된 경계 사용)
        all_points = np.array(points + control_points, dtype=np.float32)
        
        # 경계를 약간 확장하여 모든 점이 포함되도록 함
        x_min, y_min = np.min(all_points, axis=0) - 20
        x_max, y_max = np.max(all_points, axis=0) + 20
        
        # 범위 검사
        x_min = max(0, x_min)
        y_min = max(0, y_min)
        x_max = min(width-1, x_max)
        y_max = min(height-1, y_max)
        
        rect = (int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min))
        
        # 삼각분할 수행
        if rect[2] <= 0 or rect[3] <= 0:
            # 유효하지 않은 사각형 - 기본 확장 사용
            kernel = np.ones((7, 7), np.uint8)
            return cv2.dilate(mask, kernel, iterations=2)
            
        tri = cv2.Subdiv2D(rect)
        
        # 안전하게 점 추가
        valid_points = []
        for i, pt in enumerate(all_points):
            if (rect[0] < pt[0] < rect[0] + rect[2] and 
                rect[1] < pt[1] < rect[1] + rect[3]):
                try:
                    tri.insert((pt[0], pt[1]))
                    valid_points.append(i)  # 유효한 점 인덱스 저장
                except:
                    pass
        
        if len(valid_points) < 3:
            # 유효한 점이 너무 적음 - 기본 확장 사용
            kernel = np.ones((7, 7), np.uint8)
            return cv2.dilate(mask, kernel, iterations=2)
        
        # 삼각형 목록 가져오기
        try:
            triangles = tri.getTriangleList()
        except cv2.error:
            # 삼각분할 실패 - 기본 확장 사용
            kernel_size = 9 if is_head else 7
            iterations = 3 if is_head else 2
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            return cv2.dilate(mask, kernel, iterations=iterations)
            
        triangle_indices = []
        
        for t in triangles:
            pt1 = (t[0], t[1])
            pt2 = (t[2], t[3])
            pt3 = (t[4], t[5])
            
            # 더 유연한 점 매칭 (특히 머리 영역)
            atol_value = 2.0 if is_head else 1.0
            idx1 = next((i for i, p in enumerate(all_points) if np.allclose(p, pt1, atol=atol_value)), None)
            idx2 = next((i for i, p in enumerate(all_points) if np.allclose(p, pt2, atol=atol_value)), None)
            idx3 = next((i for i, p in enumerate(all_points) if np.allclose(p, pt3, atol=atol_value)), None)
            
            if idx1 is not None and idx2 is not None and idx3 is not None:
                triangle_indices.append(np.array([idx1, idx2, idx3], dtype=np.int32))
        
        # 삼각형이 충분한지 확인
        if len(triangle_indices) < 2:
            # 삼각형이 부족함 - 기본 확장 사용
            kernel_size = 9 if is_head else 7
            iterations = 3 if is_head else 2
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            return cv2.dilate(mask, kernel, iterations=iterations)
            # 삼각형이 부족함 - 기본 확장 사용
            kernel = np.ones((7, 7), np.uint8)
            return cv2.dilate(mask, kernel, iterations=2)
        
        # ARAP 적용
        np_control_points = np.array(control_points, dtype=np.float32)
        np_target_points = np.array(target_points, dtype=np.float32)
        
        arap = ARAP(np_control_points, triangle_indices, all_points)
        deformed_points = arap.solve(np_target_points)
        
        # 변형된 윤곽선으로 새 마스크 생성
        deformed_contour = deformed_points[:len(points)].astype(np.int32)
        
        # 유효한 윤곽선인지 확인
        if len(deformed_contour) < 3:
            kernel_size = 9 if is_head else 7
            iterations = 3 if is_head else 2
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            return cv2.dilate(mask, kernel, iterations=iterations)
            
        refined_mask = np.zeros_like(mask)
        
        # 닫힌 다각형 그리기
        cv2.fillPoly(refined_mask, [deformed_contour], 255)
        
        # 머리 영역인 경우 추가 확장 적용
        if is_head:
            kernel = np.ones((5, 5), np.uint8)
            refined_mask = cv2.dilate(refined_mask, kernel, iterations=2)
        
        # 구멍 채우기
        contours, _ = cv2.findContours(refined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cv2.fillPoly(refined_mask, contours, 255)
        
        # 원본 마스크와 합치기
        refined_mask = cv2.bitwise_or(mask, refined_mask)
        
        # 마스크 후처리 (작은 구멍 채우기)
        kernel_size = 7 if is_head else 5
        iterations = 2 if is_head else 1
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        refined_mask = cv2.morphologyEx(refined_mask, cv2.MORPH_CLOSE, kernel, iterations=iterations)
        
        # 머리 영역의 경우 추가 윤곽선 처리
        if is_head:
            # 닫힌 홀 채우기를 위한 플러드필 사용
            h, w = refined_mask.shape
            flood_mask = np.zeros((h+2, w+2), np.uint8)
            seed_points = [(0, 0), (h-1, 0), (0, w-1), (h-1, w-1), (h//2, w//2)]
            
            for seed in seed_points:
                if refined_mask[min(seed[0], h-1), min(seed[1], w-1)] == 0:  # 배경점이면
                    cv2.floodFill(refined_mask, flood_mask, seed, 0)
                    
            # 윤곽선 부드럽게
            refined_mask = cv2.GaussianBlur(refined_mask, (5, 5), 0)
            _, refined_mask = cv2.threshold(refined_mask, 127, 255, cv2.THRESH_BINARY)
        
        return refined_mask
    except Exception as e:
        logging.warning(f"ARAP 마스크 개선 실패: {e}")
        # 오류 발생 시 단순 확장으로 대체
        kernel_size = 9 if is_head else 7
        iterations = 3 if is_head else 2
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        return cv2.dilate(mask, kernel, iterations=iterations)