"""
Cross-platform auto-updater for MotionSmith
Supports Sparkle (macOS), AppImageUpdate (Linux), and WinSparkle (Windows)
"""

import logging
import os
import sys
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QObject

from automataii.utils.update_config import configured_appcast_url, configured_update_url

logger = logging.getLogger(__name__)


class AutoUpdater:
    """Cross-platform auto-updater"""

    def __init__(self, app_instance: QObject | None = None) -> None:
        self.app_instance = app_instance
        self.update_url = configured_update_url(os.environ)
        self.appcast_url = configured_appcast_url(os.environ)
        self.updater: object | None = None
        self._sparkle_controller: object | None = None
        self._updater_type: str | None = None
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
        """Setup Sparkle for macOS.

        Sparkle 2 is preferred. The legacy SUUpdater path remains as a
        compatibility fallback for older bundled frameworks only; startup
        background checks still respect Sparkle's persisted/user-approved
        automatic-check state instead of forcing runtime defaults.
        """
        try:
            from objc import loadBundle

            # Find Sparkle framework
            bundle_path = self._sparkle_framework_path()
            if bundle_path is None:
                logger.info("Sparkle.framework not found in app bundle; update checks unavailable")
                return False
            if not bundle_path.exists():
                logger.warning(f"Sparkle.framework not found at {bundle_path}")
                return False

            # Load Sparkle framework
            objc_namespace: dict[str, object] = {}
            success = loadBundle("Sparkle", objc_namespace, bundle_path=str(bundle_path))

            if not success:
                logger.error("Failed to load Sparkle framework")
                return False

            if self._setup_sparkle2(objc_namespace):
                self._updater_type = "Sparkle 2"
                logger.info("Sparkle 2 updater configured successfully")
                return True

            logger.warning("Sparkle 2 controller unavailable; trying legacy SUUpdater fallback")
            if self._setup_legacy_sparkle(objc_namespace):
                self._updater_type = "Sparkle (legacy SUUpdater)"
                logger.info("Legacy Sparkle updater configured successfully")
                return True

            logger.error("No supported Sparkle updater class found")
            return False

        except ImportError:
            logger.warning("PyObjC not available for Sparkle integration")
            return False
        except Exception as e:
            logger.error(f"Sparkle setup failed: {e}")
            return False

    def _sparkle_framework_path(self) -> Path | None:
        """Return the bundled Sparkle.framework path when the app is bundled."""
        candidates: list[Path] = []

        bundle_root = getattr(sys, "_MEIPASS", None)
        if isinstance(bundle_root, str):
            root = Path(bundle_root).resolve()
            candidates.extend(
                [
                    root / "Sparkle.framework",
                    root / "Frameworks" / "Sparkle.framework",
                    root.parent / "Frameworks" / "Sparkle.framework",
                ]
            )

        executable = Path(sys.executable).resolve()
        if len(executable.parents) >= 2:
            contents_dir = executable.parents[1]
            candidates.append(contents_dir / "Frameworks" / "Sparkle.framework")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _setup_sparkle2(self, objc_namespace: dict[str, object]) -> bool:
        """Setup Sparkle 2 using SPUStandardUpdaterController."""
        controller_class = objc_namespace.get("SPUStandardUpdaterController")
        alloc = getattr(controller_class, "alloc", None)
        if not callable(alloc):
            return False

        controller = alloc()
        init = getattr(
            controller,
            "initWithStartingUpdater_updaterDelegate_userDriverDelegate_",
            None,
        )
        if not callable(init):
            return False

        controller = init(True, None, None)
        updater = self._sparkle_updater_from_controller(controller)
        if updater is None:
            logger.error("SPUStandardUpdaterController did not expose an updater")
            return False

        self._sparkle_controller = controller
        self.updater = updater

        if self.app_instance:

            def cleanup_sparkle2() -> None:
                logger.debug("Sparkle 2 cleanup is managed by the framework")

            self._connect_about_to_quit(cleanup_sparkle2)

        return True

    def _setup_legacy_sparkle(self, objc_namespace: dict[str, object]) -> bool:
        """Setup legacy Sparkle SUUpdater as a backwards-compatible fallback."""
        try:
            import Foundation

            SUUpdater = objc_namespace.get("SUUpdater")
            if not SUUpdater:
                return False

            shared_updater = getattr(SUUpdater, "sharedUpdater", None)
            if not callable(shared_updater):
                logger.error("SUUpdater.sharedUpdater is not callable")
                return False
            updater = shared_updater()

            # Set feed URL for the legacy compatibility path. Sparkle 2 should
            # use the bundled SUFeedURL Info.plist value instead.
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

            return True

        except Exception as e:
            logger.error(f"Legacy Sparkle setup failed: {e}")
            return False

    @staticmethod
    def _sparkle_updater_from_controller(controller: object) -> object | None:
        updater_accessor = getattr(controller, "updater", None)
        if callable(updater_accessor):
            return cast(object | None, updater_accessor())
        return cast(object | None, getattr(controller, "updater", None))

    @staticmethod
    def _bool_method_value(target: object, method_name: str) -> bool | None:
        method = getattr(target, method_name, None)
        if callable(method):
            return bool(method())
        value = getattr(target, method_name, None)
        if isinstance(value, bool):
            return value
        return None

    def _sparkle_automatically_checks_for_updates(self) -> bool | None:
        targets = [self.updater, self._sparkle_controller]
        for target in targets:
            if target is None:
                continue
            value = self._bool_method_value(target, "automaticallyChecksForUpdates")
            if value is not None:
                return value
        return None

    def can_check_for_updates_in_background(self) -> bool:
        """Return whether a silent startup check is allowed right now."""
        if self.platform != "darwin" or self.updater is None:
            return False

        check_background = getattr(self.updater, "checkForUpdatesInBackground", None)
        if not callable(check_background):
            return False

        automatically_checks = self._sparkle_automatically_checks_for_updates()
        if automatically_checks is not True:
            logger.debug(
                "Skipping background update check because Sparkle automatic checks are disabled "
                "or unavailable."
            )
            return False
        return True

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
                    target = self._sparkle_controller or self.updater
                    check = getattr(target, "checkForUpdates_", None)
                    if callable(check):
                        check(None)
                        return True
                else:
                    if not self.can_check_for_updates_in_background():
                        return False
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
            "startup_background_check_allowed": self.can_check_for_updates_in_background(),
        }

        if self.platform == "darwin":
            info["updater_type"] = self._updater_type or "Sparkle"
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
