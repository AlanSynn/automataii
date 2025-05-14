# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Homebrew Python 라이브러리 경로 찾기
# 이 경로는 사용자 환경에 따라 다를 수 있습니다.
python_lib_path = os.path.join(sys.prefix, '..', '..', 'Frameworks', 'Python.framework', 'Versions', '3.13', 'Python')
if not os.path.exists(python_lib_path):
    # 대체 경로 (예: /usr/local/opt/python@3.13/Frameworks/...)
    # 필요한 경우 여기에 다른 경로 탐색 로직을 추가할 수 있습니다.
    print(f"WARNING: Python library not found at primary path: {python_lib_path}")
    # 직접 명시
    python_lib_path = '/usr/local/Cellar/python@3.13/3.13.5/Frameworks/Python.framework/Versions/3.13/Python'

print(f"Using Python library: {python_lib_path}")

a = Analysis(
    ['app.py'],
    pathex=['src'],
    binaries=[(python_lib_path, '.')],
    datas=[('resources', 'resources'), ('models', 'models'), ('models/onnx', 'models/onnx')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Automataii',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Automataii',
)
app = BUNDLE(
    coll,
    name='Automataii.app',
    icon='resources/icons/AppIcon.icns',
    bundle_identifier='com.alansynn.automataii',
)
