# Quick Build Guide for Automataii

## TL;DR - Build Now

```bash
# 1. Install platform dependencies (one-time setup)
uv add --optional build-macos    # macOS only
# uv add --optional build-windows  # Windows only

# 2. Build the application
uv run python build/build_simple.py
```

That's it! Your built application will be in the `dist/` folder.

## What You Get

- **macOS**: `dist/Automataii.app` - Ready to use application bundle
- **Linux**: `dist/Automataii/` - Executable directory 
- **Windows**: `dist/Automataii.exe` - Standalone executable

## First Time Setup

### 1. Install uv (if needed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install project dependencies
```bash
uv sync
```

### 3. Install platform-specific build tools

**macOS:**
```bash
uv add --optional build-macos
```

**Windows:**
```bash
uv add --optional build-windows
```

**Linux:** No additional dependencies needed.

## Build Options

### Simple Build (Recommended)
```bash
uv run python build/build_simple.py
```

### Advanced Builds with Auto-Updates
```bash
# macOS with Sparkle
uv run python build/build_macos.py

# Linux with AppImage  
uv run python build/build_linux.py

# Windows with WinSparkle
uv run python build/build_windows.py
```

### Universal Build Script
```bash
uv run python build/build.py --platform auto
```

## Troubleshooting

### Build Fails with Import Errors

**Check dependencies:**
```bash
uv run python -c "import PyInstaller, onnxruntime, PyQt6; print('OK')"
```

**If that fails:**
```bash
uv sync --reinstall
```

### PyInstaller Not Found

```bash
uv add pyinstaller  # Should be automatic, but just in case
```

### Platform Dependencies Missing

**macOS:**
```bash
uv add pyobjc-core pyobjc-framework-Cocoa
```

**Windows:**
```bash
uv add pywin32
```

### Application Won't Start

**Test the source first:**
```bash
uv run python src/automataii/__main__.py
```

**If that works but build doesn't:**
```bash
# Clean and rebuild
uv run python build/build_simple.py --clean-only
uv run python build/build_simple.py
```

## Testing Your Build

**macOS:**
```bash
./dist/Automataii.app/Contents/MacOS/Automataii
```

**Linux:**
```bash
./dist/Automataii/Automataii
```

**Windows:**
```bash
./dist/Automataii.exe
```

## Distribution

Your built application is completely self-contained and can be:

1. **Shared directly** - Copy the `dist/` contents to other machines
2. **Created into installers** - Use the advanced build scripts for DMG/AppImage/NSIS installers
3. **Distributed via CI/CD** - Use the GitHub Actions workflow for automated releases

## Need Help?

1. **Build issues**: Check the error messages carefully
2. **Missing files**: Look in the spec file (`automataii.spec`) 
3. **Runtime issues**: Test the source version first
4. **Platform problems**: Check the platform-specific build scripts

The simple build script should work for 90% of use cases. Use the advanced scripts only if you need auto-update functionality or custom installers.