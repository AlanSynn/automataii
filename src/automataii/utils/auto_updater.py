"""
Cross-platform auto-updater for MotionSmith
Supports Sparkle (macOS), AppImageUpdate (Linux), and WinSparkle (Windows)
"""

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)


class AutoUpdater:
    """Cross-platform auto-updater"""

    def __init__(self, app_instance: QObject | None = None) -> None:
        self.app_instance = app_instance
        self.update_url = "https://github.com/automataii/automataii/releases/latest"
        self.appcast_url = (
            "https://github.com/automataii/automataii/releases/latest/download/appcast.xml"
        )
        self.updater: object | None = None
        self.platform = sys.platform

    def setup_updater(self) -> bool:
        """Setup platform-specific updater"""
        try:
            if self.platform == "darwin":
                return self._setup_sparkle()
            elif self.platform == "win32":
                return self._setup_winsparkle()
            elif self.platform.startswith("linux"):
                return self._setup_appimage_update()
            else:
                logger.warning(f"Auto-updates not supported on {self.platform}")
                return False
        except Exception as e:
            logger.error(f"Failed to setup auto-updater: {e}")
            return False

    def _connect_about_to_quit(self, callback: object) -> None:
        """Connect a cleanup callback when the Qt app exposes aboutToQuit."""
        if self.app_instance is None:
            return
        about_to_quit = getattr(self.app_instance, "aboutToQuit", None)
        connect = getattr(about_to_quit, "connect", None)
        if callable(connect):
            connect(callback)

    def _setup_sparkle(self) -> bool:
        """Setup Sparkle for macOS"""
        try:
            # Check if running from app bundle
            bundle_root = getattr(sys, "_MEIPASS", None)
            if not isinstance(bundle_root, str):
                logger.info("Not running from bundle, skipping Sparkle setup")
                return False

            import Foundation
            from objc import loadBundle

            # Find Sparkle framework
            bundle_path = Path(bundle_root).parent / "Frameworks" / "Sparkle.framework"
            if not bundle_path.exists():
                logger.warning(f"Sparkle.framework not found at {bundle_path}")
                return False

            # Load Sparkle framework
            objc_namespace: dict[str, object] = {}
            success = loadBundle("Sparkle", objc_namespace, bundle_path=str(bundle_path))

            if not success:
                logger.error("Failed to load Sparkle framework")
                return False

            # Get SUUpdater class
            SUUpdater = objc_namespace.get("SUUpdater")
            if not SUUpdater:
                logger.error("SUUpdater class not found")
                return False

            shared_updater = getattr(SUUpdater, "sharedUpdater", None)
            if not callable(shared_updater):
                logger.error("SUUpdater.sharedUpdater is not callable")
                return False
            updater = shared_updater()

            # Configure updater
            for method_name, value in (
                ("setAutomaticallyChecksForUpdates_", True),
                ("setAutomaticallyDownloadsUpdates_", False),
                ("setUpdateCheckInterval_", 24 * 60 * 60),
            ):
                method = getattr(updater, method_name, None)
                if callable(method):
                    method(value)

            # Set feed URL
            NSURL = Foundation.NSURL
            feed_url = NSURL.URLWithString_(self.appcast_url)
            set_feed_url = getattr(updater, "setFeedURL_", None)
            if callable(set_feed_url):
                set_feed_url(feed_url)
            self.updater = updater

            # Setup cleanup on app quit
            if self.app_instance:

                def cleanup_sparkle() -> None:
                    try:
                        if self.updater:
                            # Sparkle cleanup is automatic
                            pass
                    except Exception as e:
                        logger.debug(f"Sparkle cleanup: {e}")

                self._connect_about_to_quit(cleanup_sparkle)

            logger.info("Sparkle updater configured successfully")
            return True

        except ImportError:
            logger.warning("PyObjC not available for Sparkle integration")
            return False
        except Exception as e:
            logger.error(f"Sparkle setup failed: {e}")
            return False

    def _setup_winsparkle(self) -> bool:
        """Setup WinSparkle for Windows"""
        try:
            import ctypes

            # Find WinSparkle DLL
            dll_path = None
            bundle_root = getattr(sys, "_MEIPASS", None)
            search_paths = [
                os.path.join(bundle_root, "WinSparkle.dll")
                if isinstance(bundle_root, str)
                else None,
                os.path.join(os.path.dirname(sys.executable), "WinSparkle.dll"),
                "WinSparkle.dll",  # System PATH
            ]

            for path in search_paths:
                if path and os.path.exists(path):
                    dll_path = path
                    break

            if not dll_path:
                logger.warning("WinSparkle.dll not found")
                return False

            # Load WinSparkle DLL
            win_dll = getattr(ctypes, "WinDLL", None)
            if not callable(win_dll):
                logger.warning("ctypes.WinDLL is not available on this platform")
                return False
            winsparkle = win_dll(dll_path)

            # Define function signatures
            winsparkle.win_sparkle_set_appcast_url.argtypes = [ctypes.c_char_p]
            winsparkle.win_sparkle_set_appcast_url.restype = None

            winsparkle.win_sparkle_set_app_details.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
            ]
            winsparkle.win_sparkle_set_app_details.restype = None

            winsparkle.win_sparkle_init.argtypes = []
            winsparkle.win_sparkle_init.restype = None

            winsparkle.win_sparkle_cleanup.argtypes = []
            winsparkle.win_sparkle_cleanup.restype = None

            winsparkle.win_sparkle_check_update_with_ui.argtypes = []
            winsparkle.win_sparkle_check_update_with_ui.restype = None

            # Configure WinSparkle
            winsparkle.win_sparkle_set_app_details("MotionSmith", "MotionSmith", "0.1.0")
            winsparkle.win_sparkle_set_appcast_url(self.appcast_url.encode("utf-8"))

            # Initialize WinSparkle
            winsparkle.win_sparkle_init()

            # Setup cleanup
            if self.app_instance:

                def cleanup_winsparkle() -> None:
                    try:
                        winsparkle.win_sparkle_cleanup()
                    except Exception as e:
                        logger.debug(f"WinSparkle cleanup: {e}")

                self._connect_about_to_quit(cleanup_winsparkle)

            self.updater = winsparkle
            logger.info("WinSparkle updater configured successfully")
            return True

        except Exception as e:
            logger.error(f"WinSparkle setup failed: {e}")
            return False

    def _setup_appimage_update(self) -> bool:
        """Setup AppImageUpdate for Linux"""
        try:
            # Check if running from AppImage
            appimage_path = os.environ.get("APPIMAGE")
            if not appimage_path:
                logger.info("Not running from AppImage, skipping update setup")
                return False

            # AppImageUpdate is handled externally by the AppImage runtime
            # We just need to set up the update information
            logger.info("AppImage update support detected")

            # The actual update mechanism is built into the AppImage
            # Users can update by running: ./MotionSmith.AppImage --appimage-update

            return True

        except Exception as e:
            logger.error(f"AppImage update setup failed: {e}")
            return False

    def check_for_updates(self, show_ui: bool = True) -> bool:
        """Manually check for updates"""
        try:
            if not self.updater:
                logger.warning("Updater not initialized")
                return False

            if self.platform == "darwin":
                # Sparkle update check
                if show_ui:
                    check = getattr(self.updater, "checkForUpdates_", None)
                    if callable(check):
                        check(None)
                        return True
                else:
                    check_background = getattr(self.updater, "checkForUpdatesInBackground", None)
                    if callable(check_background):
                        check_background()
                        return True
                return False

            elif self.platform == "win32":
                # WinSparkle update check
                check = getattr(self.updater, "win_sparkle_check_update_with_ui", None)
                if callable(check):
                    check()
                    return True
                return False

            elif self.platform.startswith("linux"):
                # For AppImage, we can show a message to the user
                if show_ui:
                    self._show_appimage_update_dialog()
                return True

            return False

        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return False

    def _show_appimage_update_dialog(self) -> None:
        """Show AppImage update dialog"""
        try:
            from PyQt6.QtCore import QProcess
            from PyQt6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                None,
                "Check for Updates",
                "Would you like to check for updates?\n\nThis will download the latest version if available.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Try to run AppImageUpdate
                appimage_path = os.environ.get("APPIMAGE")
                if appimage_path:
                    process = QProcess()
                    process.start(appimage_path, ["--appimage-update"])
                    if process.waitForStarted():
                        logger.info("AppImage update process started")
                    else:
                        # Fallback: open browser to releases page
                        import webbrowser

                        webbrowser.open(self.update_url)

        except Exception as e:
            logger.error(f"AppImage update dialog failed: {e}")

    def get_update_info(self) -> dict[str, str | bool | None]:
        """Get information about update mechanism"""
        info: dict[str, str | bool | None] = {
            "platform": self.platform,
            "updater_available": self.updater is not None,
            "update_url": self.update_url,
            "appcast_url": self.appcast_url,
        }

        if self.platform == "darwin":
            info["updater_type"] = "Sparkle"
        elif self.platform == "win32":
            info["updater_type"] = "WinSparkle"
        elif self.platform.startswith("linux"):
            info["updater_type"] = "AppImageUpdate"
            info["appimage_path"] = os.environ.get("APPIMAGE")

        return info


def setup_auto_updater(app_instance: QObject | None) -> AutoUpdater | None:
    """Setup auto-updater for the application"""
    try:
        updater = AutoUpdater(app_instance)
        if updater.setup_updater():
            return updater
        else:
            logger.info("Auto-updater not available on this platform/configuration")
            return None
    except Exception as e:
        logger.error(f"Failed to setup auto-updater: {e}")
        return None
