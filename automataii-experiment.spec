# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files

# Increase recursion limit for complex projects
sys.setrecursionlimit(5000)

# Create entry script for experiment mode
entry_script = """
import sys
sys.argv.append('--experiment')
from automataii.__main__ import main
if __name__ == "__main__":
    main()
"""

with open('automataii_experiment_entry.py', 'w') as f:
    f.write(entry_script)

a = Analysis(
    ['automataii_experiment_entry.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('models/onnx', 'models/onnx'),
        ('src/automataii/gui/fonts', 'automataii/gui/fonts'),
        ('config', 'config'),
        ('src/automataii/kinematics/generated_mechanism_paths.json', 'automataii/kinematics'),
        ('src/automataii/modules', 'automataii/modules'),
        # Only include root-level images from examples directory
        ('src/examples/*.png', 'examples/'),
        ('resources/', 'resources/'),
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
    name='AutomataII-Experiment',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS app bundle configuration
app = BUNDLE(
    exe,
    name='AutomataII-Experiment.app',
    icon='resources/icons/AppIcon.icns',
    bundle_identifier='com.alansynn.automataii.experiment',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [],
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13.0',
        'NSHumanReadableCopyright': 'Copyright © 2024 Alan Synn. All rights reserved.',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleDisplayName': 'AutomataII Experiment',
        'LSApplicationCategoryType': 'public.app-category.graphics-design',
        # Experiment-specific identifier
        'CFBundleIdentifier': 'com.alansynn.automataii.experiment',
    }
)