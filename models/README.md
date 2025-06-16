# Models Directory

이 디렉토리는 성공적으로 검증된 MMPose/MMDetection 모델과 ONNX 변환 파이프라인을 포함합니다.

## 디렉토리 구조

```
models/
├── configs/                     # 모델 설정 파일
│   ├── detector_config.py      # MaskRCNN 검출기 설정
│   └── pose_config.py          # TopDown 포즈 추정기 설정
├── weights/                     # PyTorch 모델 가중치
│   ├── detector_latest.pth     # 검출기 가중치 (335MB)
│   └── pose_best_AP_epoch_72.pth # 포즈 추정기 가중치 (390MB)
├── pytorch/                     # PyTorch 추론 스크립트
│   └── process_legacy_api.py   # Legacy API 기반 추론 (검증됨)
├── onnx/                       # ONNX 모델과 추론 스크립트
│   ├── detector_backbone.onnx  # 검출기 백본 ONNX (89.6MB)
│   ├── pose_model.onnx         # 포즈 추정기 ONNX (129.6MB)
│   └── test_onnx_inference.py  # ONNX 추론 테스트 (성공)
└── test_complete_legacy.py     # 전체 파이프라인 테스트
```

## 검증된 파이프라인

### 1. PyTorch 추론 (Legacy API)
```bash
python models/pytorch/process_legacy_api.py --image astronaut.png \
  --det-config models/configs/detector_config.py \
  --det-checkpoint models/weights/detector_latest.pth \
  --pose-config models/configs/pose_config.py \
  --pose-checkpoint models/weights/pose_best_AP_epoch_72.pth
```

### 2. ONNX 추론 (검증됨)
```bash
python models/onnx/test_onnx_inference.py \
  --image astronaut.png \
  --detector-onnx models/onnx/detector_backbone.onnx \
  --pose-onnx models/onnx/pose_model.onnx
```

### 3. 전체 테스트
```bash
python models/test_complete_legacy.py
```

## 모델 사양

### 검출기 (MaskRCNN)
- **백본**: ResNet-50 with FPN
- **전처리**:
  - 크기 조정: (1333, 800) keep_ratio=True
  - 패딩: size_divisor=32
  - 정규화: mean=[103.53, 116.28, 123.675], std=[1.0, 1.0, 1.0]
  - 색상: BGR (to_rgb=False)

### 포즈 추정기 (TopDown)
- **입력 크기**: (192, 256)
- **키포인트**: COCO 17개 관절
- **전처리**:
  - 크기 조정: (192, 256)
  - 색상 변환: BGR → RGB
  - 정규화: ImageNet 평균/표준편차

## ONNX 변환 세부사항

### 검출기 ONNX
- 백본만 변환 (안정성을 위해)
- 동적 축: batch_size, height, width
- Opset 버전: 11

### 포즈 추정기 ONNX
- 전체 모델 변환
- 히트맵 출력 → 키포인트 추출
- 동적 축: batch_size

## 성능 검증

✅ **PyTorch 추론**: 완전 작동
✅ **ONNX 추론**: 완전 작동
✅ **키포인트 추출**: 정확성 검증됨
✅ **결과 시각화**: image_to_annotations.py 스타일
✅ **파일 출력**:
- image.png
- bounding_box.yaml
- char_cfg.yaml
- texture.png
- mask.png
- joint_overlay.png

## 사용법

1. **환경 설정**:
   ```bash
   pip install mmdet mmpose mmcv-full onnxruntime opencv-python
   ```

2. **PyTorch 추론**:
   ```bash
   cd models
   python pytorch/process_legacy_api.py --image ../astronaut.png
   ```

3. **ONNX 추론**:
   ```bash
   cd models
   python onnx/test_onnx_inference.py --image ../astronaut.png
   ```

## 주요 특징

- **Legacy API 호환**: mmdet/mmpose legacy API 사용으로 안정성 확보
- **PyTorch 2.6+ 호환**: torch.load monkey patch 적용
- **완전한 파이프라인**: 검출 → 크롭 → 포즈 추정 → 결과 포맷팅
- **ONNX 배포 준비**: 프로덕션 환경에서 사용 가능한 ONNX 모델
- **결과 호환성**: 기존 image_to_annotations.py와 동일한 출력 형식