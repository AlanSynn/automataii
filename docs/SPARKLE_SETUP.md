# Sparkle Auto-Update Setup Guide

이 가이드는 Automataii 앱의 Sparkle 자동 업데이트 시스템을 설정하는 방법을 설명합니다.

## 🚀 GitHub Repository 설정

### 1. GitHub Pages 활성화
1. Repository → Settings → Pages
2. Source: "GitHub Actions" 선택
3. 저장

### 2. GitHub Secrets 설정
Repository → Settings → Secrets and variables → Actions에서 다음 secrets 추가:

#### `SPARKLE_PRIVATE_KEY` (선택사항)
- Sparkle EdDSA 서명을 위한 개인 키
- 생성 방법:
```bash
# Sparkle 다운로드 후
./bin/generate_keys
# sparkle_private_key 파일 내용을 복사해서 GitHub Secret에 추가
```

#### `SPARKLE_PUBLIC_KEY` (선택사항)
- EdDSA 공개 키
- `sparkle_public_key` 파일 내용을 복사

### 3. Repository 권한 설정
Repository → Settings → Actions → General:
- "Read and write permissions" 선택
- "Allow GitHub Actions to create and approve pull requests" 체크

## 📦 릴리스 프로세스

### 자동 릴리스 (권장)
```bash
# 새 버전 태그 생성 및 푸시
git tag v1.0.1
git push origin v1.0.1
```

GitHub Actions가 자동으로:
1. 멀티플랫폼 빌드 (macOS DMG, Linux AppImage, Windows EXE)
2. Sparkle appcast 생성
3. GitHub 릴리스 생성
4. GitHub Pages에 appcast 배포

### 수동 릴리스
Repository → Actions → "Build and Release" → "Run workflow"

## 🔧 Appcast URL

앱은 다음 URL에서 업데이트를 확인합니다:
```
https://alansynn.github.io/automataii/appcast/appcast.xml
```

이 URL은 `automataii.spec` 파일의 `SUFeedURL`에 설정되어 있습니다.

## 📱 사용자 경험

1. 앱 실행 시 자동으로 업데이트 확인 (24시간 간격)
2. 새 버전 발견 시 업데이트 다이얼로그 표시
3. 사용자가 승인하면 자동 다운로드 및 설치
4. 앱 재시작으로 업데이트 완료

## 🛠 고급 설정

### 업데이트 주기 변경
`automataii.spec`에서 `SUScheduledCheckInterval` 값 수정:
```python
'SUScheduledCheckInterval': 86400,  # 초 단위 (86400 = 24시간)
```

### 수동 업데이트 체크 비활성화
```python
'SUEnableAutomaticChecks': False,
```

### 릴리스 노트 추가
GitHub 릴리스 생성 시 description에 릴리스 노트를 작성하면 자동으로 appcast에 포함됩니다.

## 🔍 문제 해결

### 업데이트가 감지되지 않는 경우
1. appcast URL 확인: https://alansynn.github.io/automataii/appcast/appcast.xml
2. GitHub Pages 배포 상태 확인
3. 앱의 현재 버전과 릴리스 버전 비교

### 빌드 실패
1. GitHub Actions 로그 확인
2. 의존성 설치 오류 확인
3. 코드 서명 설정 확인 (macOS)

## 📋 체크리스트

설정 완료 확인:
- [ ] GitHub Pages 활성화됨
- [ ] Sparkle keys 생성 및 secrets 설정
- [ ] Repository 권한 설정 완료
- [ ] 첫 릴리스 태그 생성 및 테스트
- [ ] appcast URL 접근 가능 확인
- [ ] 앱에서 업데이트 메뉴 동작 확인

이제 완전한 자동 업데이트 시스템이 준비되었습니다! 🎉