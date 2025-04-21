#!/usr/bin/env python3
"""
Universal build script for Automataii
Supports building for macOS, Linux, and Windows
"""

import sys
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Build Automataii for current platform')
    parser.add_argument('--platform', choices=['macos', 'linux', 'windows', 'auto'], 
                       default='auto', help='Target platform (auto-detect by default)')
    parser.add_argument('--sign', type=str, help='Code signing identity (macOS only)')
    parser.add_argument('--no-dmg', action='store_true', help='Skip DMG creation (macOS only)')
    parser.add_argument('--no-installer', action='store_true', help='Skip installer creation (Windows only)')
    parser.add_argument('--no-zsync', action='store_true', help='Skip zsync file creation (Linux only)')
    parser.add_argument('--update-url', type=str, help='Update server URL (Linux only)')
    
    args = parser.parse_args()
    
    # Auto-detect platform if not specified
    if args.platform == 'auto':
        if sys.platform == 'darwin':
            args.platform = 'macos'
        elif sys.platform.startswith('linux'):
            args.platform = 'linux'
        elif sys.platform == 'win32':
            args.platform = 'windows'
        else:
            logger.error(f"Unsupported platform: {sys.platform}")
            return 1
    
    logger.info(f"Building for platform: {args.platform}")
    
    # Import and run platform-specific builder
    try:
        if args.platform == 'macos':
            from build_macos import MacOSBuilder
            builder = MacOSBuilder(Path(__file__).parent.parent)
            success = builder.build(
                sign_identity=args.sign,
                create_dmg=not args.no_dmg
            )
        
        elif args.platform == 'linux':
            from build_linux import LinuxBuilder
            builder = LinuxBuilder(Path(__file__).parent.parent)
            success = builder.build(
                update_url=args.update_url,
                create_zsync=not args.no_zsync
            )
        
        elif args.platform == 'windows':
            from build_windows import WindowsBuilder
            builder = WindowsBuilder(Path(__file__).parent.parent)
            success = builder.build(
                create_installer=not args.no_installer
            )
        
        else:
            logger.error(f"Unsupported platform: {args.platform}")
            return 1
        
        return 0 if success else 1
    
    except ImportError as e:
        logger.error(f"Failed to import platform builder: {e}")
        logger.error("Make sure all required dependencies are installed.")
        return 1
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())