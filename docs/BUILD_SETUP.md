# Build Setup Guide for Automataii

This guide shows how to set up and build Automataii using `uv` for dependency management.

## Prerequisites

1. **Install uv** (if not already installed):
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Python 3.13+** (uv will handle this automatically)

## Setup Development Environment

1. **Clone and setup project**:
   ```bash
   cd /path/to/automataii
   uv sync
   ```

2. **Install platform-specific build dependencies**:
   
   **macOS:**
   ```bash
   uv add --optional build-macos
   ```
   
   **Windows:**
   ```bash
   uv add --optional build-windows
   ```
   
   **Linux:** (no additional dependencies needed)

## Building the Application

### Option 1: Simple Build (Recommended)

```bash
# Activate uv environment
uv run python build/build_simple.py
```

### Option 2: Platform-Specific Builds

```bash
# macOS
uv run python build/build_macos.py

# Linux  
uv run python build/build_linux.py

# Windows
uv run python build/build_windows.py
```

### Option 3: Universal Build Script

```bash
uv run python build/build.py --platform auto
```

## Troubleshooting

### Common Issues

**1. PyInstaller not found:**
```bash
# PyInstaller should be installed automatically, but if not:
uv add pyinstaller
```

**2. Platform dependencies missing:**
```bash
# macOS
uv add pyobjc-core pyobjc-framework-Cocoa

# Windows  
uv add pywin32
```

**3. Build fails with import errors:**
```bash
# Check that you're in the uv environment
uv run python -c "import automataii"

# If that fails, install in development mode
uv pip install -e .
```

**4. onnxruntime not found:**
```bash
# Should be installed automatically, but if not:
uv add onnxruntime
```

### Environment Verification

Check your environment setup:
```bash
# Verify uv environment
uv run python -c "import sys; print(sys.executable)"

# Check key dependencies
uv run python -c "import PyInstaller, onnxruntime, PyQt6; print('All dependencies OK')"

# Check project can import
uv run python -c "from automataii.gui.main_window import AutomataDesigner; print('Import OK')"
```

## Build Output

After successful build, you'll find:

**macOS:**
- `dist/Automataii.app` - Application bundle
- `dist/Automataii-*.dmg` - Installer (if created)

**Linux:**
- `dist/Automataii` - Executable directory
- `dist/Automataii-*.AppImage` - Portable application (if created)

**Windows:**
- `dist/Automataii.exe` - Standalone executable
- `dist/Automataii-Setup-*.exe` - Installer (if created)

## Testing the Build

```bash
# Test the built application
# macOS
./dist/Automataii.app/Contents/MacOS/Automataii

# Linux
./dist/Automataii/Automataii

# Windows
./dist/Automataii.exe
```

## Advanced Configuration

### Custom Spec File

The build process uses `automataii.spec`. To regenerate or customize:

```bash
# Generate new spec file
uv run pyinstaller --name Automataii --windowed src/automataii/__main__.py

# Edit automataii.spec as needed, then build with:
uv run pyinstaller automataii.spec
```

### Adding Data Files

Edit `automataii.spec` to include additional files:

```python
# In automataii.spec
datas=[
    ('path/to/data/file', 'destination/in/app'),
    ('assets/*', 'assets'),
]
```

### Environment Variables

Set these for advanced builds:

```bash
# Enable debug mode
export PYINSTALLER_DEBUG=1

# Custom paths
export PYTHONPATH=/path/to/automataii/src

# Platform-specific settings  
export MACOSX_DEPLOYMENT_TARGET=10.15  # macOS
```

## CI/CD Integration

For automated builds, use:

```yaml
# In GitHub Actions
- name: Setup uv
  uses: astral-sh/setup-uv@v1

- name: Install dependencies
  run: uv sync

- name: Build application
  run: uv run python build/build_simple.py
```

## Getting Help

If you encounter issues:

1. Check the build logs for specific error messages
2. Verify all dependencies are installed with `uv list`
3. Try a clean build: `uv run python build/build_simple.py --clean-only && uv run python build/build_simple.py`
4. Check GitHub Issues for similar problems
5. Create a new issue with build logs and environment details