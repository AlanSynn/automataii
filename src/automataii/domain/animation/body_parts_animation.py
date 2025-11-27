#!/usr/bin/env python


import cv2
import numpy as np

from automataii.domain.animation.arap import ARAP


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
    contours, _ = cv2.findContours(
        part_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
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
        if (
            rect[0] < point[0] < rect[0] + rect[2]
            and rect[1] < point[1] < rect[1] + rect[3]
        ):
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
        idx1 = next(
            (i for i, p in enumerate(points) if np.allclose(p, pt1, atol=1.0)), None
        )
        idx2 = next(
            (i for i, p in enumerate(points) if np.allclose(p, pt2, atol=1.0)), None
        )
        idx3 = next(
            (i for i, p in enumerate(points) if np.allclose(p, pt3, atol=1.0)), None
        )

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
            src_tri = np.array(
                [vertices[triangle[0]], vertices[triangle[1]], vertices[triangle[2]]],
                dtype=np.float32,
            )
            dst_tri = np.array(
                [
                    deformed_vertices[triangle[0]],
                    deformed_vertices[triangle[1]],
                    deformed_vertices[triangle[2]],
                ],
                dtype=np.float32,
            )

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
                            dst_x = (
                                warp_mat[0, 0] * x + warp_mat[0, 1] * y + warp_mat[0, 2]
                            )
                            dst_y = (
                                warp_mat[1, 0] * x + warp_mat[1, 1] * y + warp_mat[1, 2]
                            )
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


def animate_body_part(
    part_image, part_mask, control_points, animation_keyframes, num_frames=30
):
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
                frames.append(
                    deform_body_part(
                        part_image, part_mask, control_points, start_keyframe
                    )
                )
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
                deformed_frame = deform_body_part(
                    part_image, part_mask, control_points, current_points
                )
                frames.append(deformed_frame)
            except Exception as e:
                print(f"보간 프레임 생성 실패: {e}")
                frames.append(part_image)

        # 마지막 키프레임만 추가 (마지막 반복에서)
        if i == keyframe_count - 2:
            try:
                frames.append(
                    deform_body_part(
                        part_image, part_mask, control_points, end_keyframe
                    )
                )
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

    if output_path.endswith(".gif"):
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

    elif output_path.endswith(".mp4"):
        # MP4로 저장
        height, width = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
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
