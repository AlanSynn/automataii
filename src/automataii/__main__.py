import argparse
import logging
import os
import platform
import sys
from pathlib import Path
from typing import NoReturn

if not os.environ.get("QT_QPA_PLATFORM"):
    ci_mode_enabled = os.environ.get("CI", "").lower() in {
        "1",
        "true",
        "yes",
    } or os.environ.get("CODEX_CI", "").lower() in {"1", "true", "yes"}
    if ci_mode_enabled:
        # Avoid hard crashes from unavailable GUI services in CI/headless runs.
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PyQt6.QtCore import QRect, Qt, QTimer
    from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication, QSplashScreen
except ImportError:
    try:
        from PySide6.QtCore import QRect, Qt, QTimer  # type: ignore[no-redef]
        from PySide6.QtGui import (  # type: ignore[no-redef]
            QBrush,
            QColor,
            QFont,
            QPainter,
            QPen,
            QPixmap,
        )
        from PySide6.QtWidgets import QApplication, QSplashScreen  # type: ignore[no-redef]
    except ImportError:
        print(
            "This application requires PyQt6 or PySide6; please install one of these packages.",
            file=sys.stderr,
        )
        sys.exit(1)

from automataii.presentation.qt.main_window import AutomataDesigner
from automataii.scenarios import run_blueprint_export_scenario
from automataii.utils.auto_updater import setup_auto_updater
from automataii.utils.config import AppConfig
from automataii.utils.logging_config import setup_logging
from automataii.utils.paths import get_app_data_dir, get_base_path, get_project_root, resolve_path
from automataii.utils.styling import LIGHT_STYLE

SPLASH_LOGO_RELATIVE_PATH = "resources/img/landing.png"
SPLASH_WIDTH = 560
SPLASH_HEIGHT = 340


def schedule_startup_update_check(
    updater: object | None,
    *,
    delay_ms: int = 3000,
    qtimer_cls: type[QTimer] = QTimer,
) -> bool:
    """Schedule a silent startup update check when the updater allows it."""
    if updater is None:
        return False

    can_check = getattr(updater, "can_check_for_updates_in_background", None)
    if not callable(can_check) or not can_check():
        return False

    check_for_updates = getattr(updater, "check_for_updates", None)
    if not callable(check_for_updates):
        return False

    qtimer_cls.singleShot(delay_ms, lambda: check_for_updates(show_ui=False))
    return True


def build_startup_splash_pixmap(
    *,
    app_name: str = AppConfig.APP_NAME,
    logo_path: Path | None = None,
) -> QPixmap | None:
    """Build the MotionSmith startup splash from the former landing-tab logo."""
    resolved_logo_path = logo_path or resolve_path(SPLASH_LOGO_RELATIVE_PATH)
    if not resolved_logo_path.exists():
        logging.warning("Startup splash logo not found: %s", resolved_logo_path)
        return None

    logo_pixmap = QPixmap(str(resolved_logo_path))
    if logo_pixmap.isNull():
        logging.warning("Startup splash logo could not be loaded: %s", resolved_logo_path)
        return None

    canvas = QPixmap(SPLASH_WIDTH, SPLASH_HEIGHT)
    canvas.fill(QColor("#ffffff"))

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setPen(QPen(QColor("#d9e3ec"), 1))
    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.drawRoundedRect(0, 0, SPLASH_WIDTH - 1, SPLASH_HEIGHT - 1, 28, 28)

    scaled_logo = logo_pixmap.scaled(
        124,
        124,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    logo_x = (SPLASH_WIDTH - scaled_logo.width()) // 2
    painter.drawPixmap(logo_x, 44, scaled_logo)

    title_font = QFont("Arial", 32)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#2f5f7f"))
    painter.drawText(
        QRect(0, 178, SPLASH_WIDTH, 58),
        Qt.AlignmentFlag.AlignCenter,
        app_name,
    )

    subtitle_font = QFont("Arial", 12)
    painter.setFont(subtitle_font)
    painter.setPen(QColor("#6c757d"))
    painter.drawText(
        QRect(0, 236, SPLASH_WIDTH, 30),
        Qt.AlignmentFlag.AlignCenter,
        "Mechanism design, animation, and physical prototyping",
    )

    painter.setPen(QColor("#9aa9b5"))
    painter.drawText(
        QRect(0, 286, SPLASH_WIDTH, 24),
        Qt.AlignmentFlag.AlignCenter,
        "Loading workspace…",
    )
    painter.end()
    return canvas


def create_startup_splash(*, app_name: str = AppConfig.APP_NAME) -> QSplashScreen | None:
    """Create a branded splash screen, or return None if the logo asset is unavailable."""
    pixmap = build_startup_splash_pixmap(app_name=app_name)
    if pixmap is None:
        return None

    splash = QSplashScreen(pixmap)
    splash.setObjectName("motionsmith_startup_splash")
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    return splash


def main() -> None:
    """Main function to initialize and run the MotionSmith application."""
    # Handle PyInstaller bundle environment
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # We're running from a PyInstaller bundle
        bundle_dir = get_base_path()
        logging.info(f"Running from PyInstaller bundle: {bundle_dir}")

        # Force macOS to use light theme for title bar
        if platform.system() == "Darwin":
            # This doesn't work for .app bundles, but kept for reference
            os.environ["QT_MAC_WANTS_LAYER"] = "1"
            os.environ["QT_QPA_PLATFORM"] = "cocoa"

            logging.info("Using bundled resource root without changing cwd: %s", bundle_dir)
    else:
        # We're running from source
        logging.info(f"Running from source: {get_project_root()}")

    parser = argparse.ArgumentParser(description="MotionSmith Application")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and features.")
    parser.add_argument(
        "--experiment",
        action="store_true",
        help="Enable experimental mode (hides Mechanism Foundry tab; Options remain in the menu).",
    )
    parser.add_argument(
        "--editing", action="store_true", help="Enable interactive segmentation editing mode."
    )
    parser.add_argument(
        "--scenario",
        choices=["blueprint-export", "image-processing"],
        help="Run an automation scenario (non-interactive) and exit.",
    )
    parser.add_argument(
        "--scenario-output",
        type=Path,
        help="Destination directory for scenario artifacts (defaults to user app data/artifacts/<scenario>).",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(console_log_level=log_level)

    if args.scenario:
        exit_code = 0
        try:
            _run_scenario(args)
        except Exception:
            logging.getLogger(__name__).exception("Scenario failed: %s", args.scenario)
            exit_code = 1
        _exit_after_scenario(exit_code)

    try:
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_EnableHighDpiScaling  # type: ignore[attr-defined]
        )
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_UseHighDpiPixmaps  # type: ignore[attr-defined]
        )
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logging.info("High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1).")
    except AttributeError:
        logging.warning(
            "Could not set High DPI attributes (Qt version might be too old or attributes moved)."
        )

    app = QApplication(sys.argv)
    app.setFont(QFont("Arial"))

    # Set application metadata
    app.setApplicationName(AppConfig.APP_NAME)
    app.setOrganizationName(AppConfig.ORGANIZATION_NAME)
    app.setOrganizationDomain(AppConfig.ORGANIZATION_DOMAIN)

    # macOS specific: Ensure app comes to foreground
    if platform.system() == "Darwin":
        try:
            import AppKit

            AppKit.NSApp.activateIgnoringOtherApps_(True)
        except ImportError:
            # Fall back to Qt method
            app.setAttribute(Qt.ApplicationAttribute.AA_PluginApplication, False)

    app.setStyleSheet(LIGHT_STYLE)

    AppConfig.initialize()
    splash = create_startup_splash()
    if splash is not None:
        splash.show()
        app.processEvents()

    # Log important paths for debugging
    logging.info(f"Project root: {get_project_root()}")
    logging.info(f"Base path: {get_base_path()}")
    logging.info(f"Current working directory: {os.getcwd()}")

    # Setup auto-updater
    updater = setup_auto_updater(app)
    if updater:
        logging.info(f"Auto-updater initialized: {updater.get_update_info()['updater_type']}")
    else:
        logging.info("Auto-updater not available")

    logging.info("Creating main window...")
    main_window = AutomataDesigner(
        debug_mode=args.debug, experiment_mode=args.experiment, editing_mode=args.editing
    )

    # Pass updater to main window if available
    if updater and hasattr(main_window, "set_updater"):
        main_window.set_updater(updater)

    main_window.show()
    if splash is not None:
        splash.finish(main_window)
        app.processEvents()

    # macOS specific: Bring window to front
    if platform.system() == "Darwin":
        main_window.raise_()
        main_window.activateWindow()

    if schedule_startup_update_check(updater):
        logging.info("Scheduled startup update check.")
    elif updater:
        logging.info("Startup update check not scheduled.")

    logging.info("Application started.")

    sys.exit(app.exec())


def _run_scenario(args: argparse.Namespace) -> None:
    scenario_name = args.scenario
    output_root = (
        Path(args.scenario_output)
        if args.scenario_output
        else get_app_data_dir() / "artifacts" / scenario_name
    )
    output_root.mkdir(parents=True, exist_ok=True)

    if scenario_name == "blueprint-export":
        svg_path = run_blueprint_export_scenario(output_root)
        manifest_path = output_root / "foundry_blueprint_manifest.json"
        metrics_path = output_root / "foundry_blueprint_metrics.json"
        logging.info(
            "Blueprint export scenario completed: svg=%s manifest=%s metrics=%s",
            svg_path,
            manifest_path,
            metrics_path,
        )
        print(f"[scenario:{scenario_name}] artifacts={svg_path}, {manifest_path}, {metrics_path}")
    elif scenario_name == "image-processing":
        from automataii.scenarios import run_image_processing_scenario

        parts_dir = run_image_processing_scenario(output_root)
        manifest_path = output_root / "image_processing_manifest.json"
        metrics_path = output_root / "image_processing_metrics.json"
        logging.info(
            "Image-processing scenario completed: parts=%s manifest=%s metrics=%s",
            parts_dir,
            manifest_path,
            metrics_path,
        )
        print(f"[scenario:{scenario_name}] artifacts={parts_dir}, {manifest_path}, {metrics_path}")
    else:
        raise ValueError(f"Unsupported scenario: {scenario_name}")


def _exit_after_scenario(exit_code: int) -> NoReturn:
    """
    Terminate automation scenarios without waiting on lingering native runtime threads.

    PyInstaller/Windows ONNXRuntime and image-processing dependencies can leave
    non-interactive smoke processes alive after the scenario artifacts are already
    written.  Scenarios are explicitly one-shot CLI automation paths, so flushing
    logs and using os._exit keeps CI and packaged smoke runs deterministic without
    affecting the normal GUI application event loop.
    """
    logging.shutdown()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(exit_code)


if __name__ == "__main__":
    main()
