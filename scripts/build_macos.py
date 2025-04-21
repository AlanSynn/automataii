import os
import shutil
import subprocess

# Define paths
SPEC_FILE = 'automataii.spec'
DIST_PATH = 'dist'
BUILD_PATH = 'build'
APP_NAME = 'AutomataII'
APP_BUNDLE_PATH = os.path.join(DIST_PATH, f'{APP_NAME}.app')

def clean():
    """Remove previous build artifacts."""
    print("--- Cleaning old build directories ---")
    if os.path.exists(DIST_PATH):
        shutil.rmtree(DIST_PATH)
    if os.path.exists(BUILD_PATH):
        shutil.rmtree(BUILD_PATH)
    print("--- Clean complete ---")

def build():
    """Run PyInstaller to build the application."""
    print(f"--- Running PyInstaller with {SPEC_FILE} ---")
    command = [
        'pyinstaller',
        '--noconfirm',
        '--clean',
        SPEC_FILE
    ]

    try:
        subprocess.run(command, check=True, text=True)
        print("--- PyInstaller build successful ---")
    except subprocess.CalledProcessError as e:
        print(f"!!! PyInstaller build failed: {e}")
        # print("\n--- STDOUT ---")
        # print(e.stdout)
        # print("\n--- STDERR ---")
        # print(e.stderr)
        exit(1)


def main():
    """Main function to run the build process."""
    clean()
    build()
    print(f"--- Build process complete. App is at {APP_BUNDLE_PATH} ---")

if __name__ == "__main__":
    main()