# -*- mode: python ; coding: utf-8 -*-

"""
Lightweight PyInstaller spec for direct CLI builds.

The primary application spec is `automataii.spec`; this variant exists for
simple cross-platform packaging and expects resources to live in the new
repository layout.
"""

a = Analysis(
    ['src/automataii/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('resources', 'resources'),
        ('models', 'models'),
        ('models/onnx', 'models/onnx'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtGui',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
    ],
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
    bundle_identifier='dev.automataii.automataii',
)
