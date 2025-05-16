# Automataii Deployment Guide

This guide explains how to build and deploy Automataii for macOS, Linux, and Windows with automatic update capabilities.

## Overview

Automataii uses a comprehensive multi-platform build system that:
- Creates native applications for macOS (.app), Linux (AppImage), and Windows (.exe)
- Integrates automatic update mechanisms (Sparkle for macOS, AppImageUpdate for Linux, WinSparkle for Windows)
- Provides GitHub Actions CI/CD for automated builds and releases
- Handles complex dependencies like `onnxruntime` and Qt frameworks

## Quick Start

### Building Locally

```bash
# Install build dependencies
pip install pyinstaller requests

# Build for current platform
cd build
python build.py

# Build for specific platform
python build.py --platform macos
python build.py --platform linux  
python build.py --platform windows
```

### Platform-Specific Options

**macOS:**
```bash
python build.py --platform macos --sign "Developer ID Application: Your Name"
```

**Linux:**
```bash
python build.py --platform linux --update-url "https://your-domain.com/releases"
```

**Windows:**
```bash
python build.py --platform windows --no-installer
```

## Build System Architecture

### Core Files

- `automataii.spec` - PyInstaller specification with platform-specific configurations
- `build/build_macos.py` - macOS build script with Sparkle integration
- `build/build_linux.py` - Linux build script with AppImage creation
- `build/build_windows.py` - Windows build script with WinSparkle integration
- `build/build.py` - Universal build script
- `.github/workflows/build-and-release.yml` - CI/CD pipeline

### Dependencies Handling

The build system automatically handles:
- **onnxruntime** - Collects all required binary files and libraries
- **Qt frameworks** - Includes necessary plugins and resources
- **Platform-specific libraries** - macOS frameworks, Linux shared libraries, Windows DLLs

## Platform-Specific Details

### macOS (.app + DMG)

**Features:**
- Native .app bundle structure
- Sparkle framework for automatic updates
- Code signing support
- DMG creation with custom layout
- Retina display support

**Requirements:**
- macOS 10.15+ for building
- Xcode command line tools
- Optional: Developer certificate for signing

**Build Process:**
1. Downloads Sparkle framework
2. Modifies `__main__.py` to include Sparkle initialization
3. Creates .app bundle with PyInstaller
4. Embeds Sparkle.framework
5. Optional: Code signing and notarization
6. Creates DMG installer

**Auto-Update:**
- Uses Sparkle framework
- Checks for updates via appcast.xml
- Supports delta updates and background downloads

### Linux (AppImage)

**Features:**
- Self-contained AppImage format
- AppImageUpdate for delta updates
- Desktop integration (.desktop file)
- zsync support for efficient updates

**Requirements:**
- Linux with GLIBC 2.17+
- Standard development tools (gcc, make)
- Optional: zsync for delta updates

**Build Process:**
1. Creates executable with PyInstaller
2. Builds AppDir structure
3. Downloads AppImageTool
4. Creates AppImage with update information
5. Generates zsync file for delta updates

**Auto-Update:**
- Uses AppImageUpdate protocol
- zsync for delta updates
- Self-updating AppImage

### Windows (.exe + Installer)

**Features:**
- Single executable or NSIS installer
- WinSparkle for automatic updates
- Windows registry integration
- Start menu and desktop shortcuts

**Requirements:**
- Windows 10+ for building
- Optional: NSIS for installer creation
- Visual C++ Redistributable (included)

**Build Process:**
1. Downloads WinSparkle library
2. Modifies `__main__.py` to include WinSparkle initialization
3. Creates executable with PyInstaller
4. Embeds WinSparkle.dll
5. Optional: Creates NSIS installer with uninstaller

**Auto-Update:**
- Uses WinSparkle library
- Windows-native update dialogs
- Registry-based configuration

## Automatic Updates

### Update Server Setup

Each platform requires an update server that provides:

**macOS (Sparkle):**
- `appcast.xml` file with version information
- DMG files hosted at stable URLs

**Linux (AppImage):**
- Latest AppImage at predictable URL
- zsync files for delta updates

**Windows (WinSparkle):**
- `appcast.xml` with Windows-specific information
- Installer files hosted at stable URLs

### Example Appcast (appcast.xml)

```xml
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>Automataii Updates</title>
    <item>
      <title>Version 0.1.0</title>
      <sparkle:version>0.1.0</sparkle:version>
      <sparkle:shortVersionString>0.1.0</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>10.15.0</sparkle:minimumSystemVersion>
      <enclosure 
        url="https://github.com/user/repo/releases/download/v0.1.0/Automataii-v0.1.0-macos.dmg" 
        length="50000000" 
        type="application/octet-stream" />
    </item>
  </channel>
</rss>
```

## GitHub Actions CI/CD

### Workflow Features

- **Multi-platform builds** - macOS, Linux, Windows in parallel
- **Automatic releases** - Creates GitHub releases with assets
- **Appcast generation** - Updates appcast.xml automatically
- **Artifact management** - Proper naming and organization

### Triggering Builds

**Tag-based release:**
```bash
git tag v0.1.0
git push origin v0.1.0
```

**Manual dispatch:**
```bash
# Through GitHub UI or API
gh workflow run build-and-release.yml -f version=v0.1.0 -f create_release=true
```

### Secrets Required

- `GITHUB_TOKEN` - Automatic (for releases)
- Optional: Code signing certificates

## Configuration

### Update URLs

Update the following URLs in the build scripts:

**macOS (build_macos.py):**
```python
feed_url = "https://your-domain.com/appcast.xml"
```

**Linux (build_linux.py):**
```python
update_info = f"zsync|{update_url}/Automataii-latest-x86_64.AppImage.zsync"
```

**Windows (build_windows.py):**
```python
appcast_url = "https://your-domain.com/appcast.xml"
```

### Version Management

Version is managed in:
- `pyproject.toml` - Python package version
- Build scripts - Extracted automatically
- GitHub Actions - From git tags

## Troubleshooting

### Common Issues

**Missing dependencies:**
```bash
# Install platform-specific tools
# macOS: brew install create-dmg
# Linux: sudo apt-get install zsync
# Windows: Install NSIS
```

**onnxruntime not found:**
- Ensure onnxruntime is installed: `pip install onnxruntime`
- Check spec file includes onnxruntime data files

**Qt plugins missing:**
- Verify Qt installation
- Check spec file includes Qt plugins directory

**Code signing fails (macOS):**
- Verify certificate is installed in Keychain
- Use correct Developer ID format
- Ensure Xcode command line tools are installed

### Debug Builds

Enable debug mode:
```bash
python build.py --platform macos 2>&1 | tee build.log
```

### Testing Updates

1. Build and sign application
2. Install on test system
3. Create fake update on server
4. Verify update mechanism works

## Security Considerations

### Code Signing

**macOS:**
- Use Developer ID certificate
- Enable hardened runtime
- Notarize for Gatekeeper

**Windows:**
- Use Authenticode certificate
- Sign both executable and installer

### Update Security

- Use HTTPS for all update URLs
- Verify checksums/signatures
- Implement rollback mechanism

## Performance Optimization

### Build Size

- Exclude unnecessary modules in spec file
- Use UPX compression (optional)
- Strip debug symbols

### Startup Time

- Minimize imports in `__main__.py`
- Use lazy loading for heavy modules
- Optimize Qt plugin loading

## Future Enhancements

### Planned Features

- Cross-compilation support
- Docker-based builds
- Automated testing in CI
- Delta updates for all platforms
- Update rollback mechanism

### Contributing

When adding new build features:
1. Update platform-specific build scripts
2. Modify GitHub Actions workflow
3. Update this documentation
4. Test on all target platforms

## Support

For build issues:
1. Check GitHub Issues
2. Review build logs
3. Test on clean environment
4. Submit detailed bug report