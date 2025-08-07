# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files

# Increase recursion limit for complex projects
sys.setrecursionlimit(5000)

a = Analysis(
    ['src/automataii/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('models/onnx', 'models/onnx'),
        ('src/automataii/gui/resources', 'automataii/gui/resources'),
        ('src/automataii/gui/fonts', 'automataii/gui/fonts'),
        ('src/automataii/kinematics/generated_mechanism_paths.json', 'automataii/kinematics'),
        ('src/automataii/macanism/appearance.json', 'automataii/macanism'),
        ('src/automataii/modules', 'automataii/modules'),
        # Only include root-level images from examples directory
        ('src/examples/*.png', 'examples'),
        ('src/examples/*.jpg', 'examples'),
        ('src/examples/*.jpeg', 'examples'),
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'PyQt6.QtGui',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'sklearn.utils._cython_blas',
        'scipy.special._cdflib',
        'onnxruntime.capi.onnxruntime_pybind11_state',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AutomataII',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Set to False for GUI applications
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/automataii/gui/resources/images/icons/cil-movie.png', # Using a placeholder icon, user can change
)

app = BUNDLE(
    exe,
    name='AutomataII.app',
    icon='src/automataii/gui/resources/images/icons/cil-movie.png', # Specify the icon for the .app bundle
    bundle_identifier='com.alansynn.automataii',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'NSRequiresAquaSystemAppearance': 'YES', # Forces light mode for the app
        'CFBundlePackageType': 'APPL',
    }
)