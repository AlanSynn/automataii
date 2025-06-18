#!/usr/bin/env python3
"""
Build script for Automataii experiment mode
Creates a build with --experiment flag automatically enabled
"""

import sys
import os
import shutil
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Build experiment version of Automataii"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    logger.info("Building Automataii in experiment mode...")

    # Clean previous builds
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        logger.info("Cleaning previous builds...")
        shutil.rmtree(dist_dir)

    # Create entry script that automatically enables experiment mode
    entry_script_content = '''#!/usr/bin/env python3
import sys
import os

# Add project src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Force experiment mode
sys.argv.append('--experiment')

# Import and run main
from automataii.__main__ import main

if __name__ == "__main__":
    main()
'''

    entry_script_path = project_root / "automataii_experiment_entry.py"
    with open(entry_script_path, 'w') as f:
        f.write(entry_script_content)

    try:
        # Build using the experiment spec file
        spec_file = project_root / "automataii-experiment.spec"
        cmd = [sys.executable, "-m", "PyInstaller", str(spec_file),
               "--clean", "--noconfirm"]

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("✓ Build completed successfully!")
            logger.info(f"Output directory: {dist_dir}")

            # List built files
            if dist_dir.exists():
                for item in dist_dir.iterdir():
                    logger.info(f"  - {item.name}")

            return True
        else:
            logger.error(f"Build failed with return code: {result.returncode}")
            logger.error(f"STDERR: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

    finally:
        # Clean up entry script
        if entry_script_path.exists():
            entry_script_path.unlink()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)