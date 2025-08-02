"""
Global Error Handler for Automataii Application

Provides comprehensive error handling, logging, and user feedback
for all application components.
"""

import logging
import sys
import traceback
from typing import Optional, Dict, Any
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from automataii.core.event_bus import get_global_event_bus
from automataii.core.events import ErrorEvent, WarningEvent


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """Error categories for better classification."""
    UI = "ui"
    KINEMATICS = "kinematics"
    MOTION_PATH = "motion_path"
    MECHANISM = "mechanism"
    PROJECT = "project"
    SKELETON = "skeleton"
    ANIMATION = "animation"
    FILE_IO = "file_io"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class GlobalErrorHandler(QObject):
    """
    Global error handler that manages all error reporting and user feedback.
    
    Features:
    - Centralized error logging
    - User-friendly error dialogs
    - Error aggregation and reporting
    - Integration with event bus
    - Automatic error recovery where possible
    """
    
    # Signals for error notifications
    error_occurred = pyqtSignal(str, str, str)  # message, category, severity
    critical_error = pyqtSignal(str)  # message
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.logger = logging.getLogger(__name__)
        self.event_bus = get_global_event_bus()
        
        # Error statistics and tracking
        self.error_count = 0
        self.warning_count = 0
        self.error_history: list[Dict[str, Any]] = []
        self.suppressed_errors: set[str] = set()
        
        # Setup exception handling
        self._setup_exception_handler()
        
        self.logger.info("GlobalErrorHandler initialized")
    
    def _setup_exception_handler(self):
        """Setup global exception handler."""
        # Store original exception handler
        self.original_excepthook = sys.excepthook
        
        # Set our custom exception handler
        sys.excepthook = self._handle_uncaught_exception
    
    def _handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow keyboard interrupts to work normally
            self.original_excepthook(exc_type, exc_value, exc_traceback)
            return
        
        # Format error message
        error_msg = f"Uncaught exception: {exc_type.__name__}: {exc_value}"
        tb_str = ''.join(traceback.format_tb(exc_traceback))
        
        # Log the error
        self.logger.critical(f"{error_msg}\nTraceback:\n{tb_str}")
        
        # Handle the error through our system
        self.handle_error(
            error_msg,
            ErrorCategory.SYSTEM,
            ErrorSeverity.CRITICAL,
            exception=exc_value,
            traceback_str=tb_str
        )
        
        # Call original handler for proper shutdown
        self.original_excepthook(exc_type, exc_value, exc_traceback)
    
    def handle_error(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        source_component: str = "Unknown",
        exception: Optional[Exception] = None,
        traceback_str: Optional[str] = None,
        show_dialog: bool = True,
        recoverable: bool = False
    ) -> bool:
        """
        Handle an error with comprehensive logging and user feedback.
        
        Args:
            message: Error message
            category: Error category
            severity: Error severity level
            source_component: Component that generated the error
            exception: Original exception if available
            traceback_str: Traceback string if available
            show_dialog: Whether to show user dialog
            recoverable: Whether the error is recoverable
            
        Returns:
            True if error was handled successfully, False otherwise
        """
        try:
            # Create error record
            error_record = {
                "message": message,
                "category": category.value,
                "severity": severity.value,
                "source_component": source_component,
                "exception": str(exception) if exception else None,
                "traceback": traceback_str,
                "recoverable": recoverable,
                "timestamp": self._get_timestamp()
            }
            
            # Add to error history
            self.error_history.append(error_record)
            
            # Update counters
            if severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
                self.error_count += 1
            elif severity == ErrorSeverity.WARNING:
                self.warning_count += 1
            
            # Log the error
            self._log_error(error_record)
            
            # Publish event
            self._publish_error_event(error_record)
            
            # Show user dialog if requested and appropriate
            if show_dialog and self._should_show_dialog(severity, message):
                self._show_error_dialog(error_record)
            
            # Emit signals
            self.error_occurred.emit(message, category.value, severity.value)
            if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
                self.critical_error.emit(message)
            
            return True
            
        except Exception as e:
            # Fallback error handling
            self.logger.critical(f"Error in error handler: {e}")
            return False
    
    def handle_warning(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        source_component: str = "Unknown",
        show_dialog: bool = False
    ):
        """Handle a warning message."""
        self.handle_error(
            message=message,
            category=category,
            severity=ErrorSeverity.WARNING,
            source_component=source_component,
            show_dialog=show_dialog,
            recoverable=True
        )
    
    def _log_error(self, error_record: Dict[str, Any]):
        """Log error record with appropriate level."""
        severity = error_record["severity"]
        message = error_record["message"]
        source = error_record["source_component"]
        
        log_msg = f"[{source}] {message}"
        
        if error_record["exception"]:
            log_msg += f" - Exception: {error_record['exception']}"
        
        if severity == "fatal":
            self.logger.critical(log_msg)
        elif severity == "critical":
            self.logger.critical(log_msg)
        elif severity == "error":
            self.logger.error(log_msg)
        elif severity == "warning":
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)
        
        # Log traceback if available
        if error_record["traceback"]:
            self.logger.debug(f"Traceback:\n{error_record['traceback']}")
    
    def _publish_error_event(self, error_record: Dict[str, Any]):
        """Publish error event to event bus."""
        if not self.event_bus:
            return
        
        try:
            if error_record["severity"] == "warning":
                event = WarningEvent(
                    warning_message=error_record["message"],
                    source_component=error_record["source_component"]
                )
            else:
                event = ErrorEvent(
                    error_message=error_record["message"],
                    error_type=error_record["category"],
                    source_component=error_record["source_component"],
                    exception=error_record.get("exception")
                )
            
            self.event_bus.publish(event)
            
        except Exception as e:
            self.logger.warning(f"Failed to publish error event: {e}")
    
    def _should_show_dialog(self, severity: ErrorSeverity, message: str) -> bool:
        """Determine if we should show a dialog for this error."""
        # Don't show dialog for suppressed errors
        if message in self.suppressed_errors:
            return False
        
        # Always show critical and fatal errors
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            return True
        
        # Show errors but not warnings by default
        if severity == ErrorSeverity.ERROR:
            return True
        
        return False
    
    def _show_error_dialog(self, error_record: Dict[str, Any]):
        """Show error dialog to user."""
        if not self.parent_widget:
            return
        
        try:
            severity = error_record["severity"]
            message = error_record["message"]
            source = error_record["source_component"]
            
            # Format dialog message
            dialog_title = f"{severity.title()} - {source}"
            dialog_message = message
            
            # Add exception info if available
            if error_record["exception"]:
                dialog_message += f"\n\nTechnical details:\n{error_record['exception']}"
            
            # Choose appropriate icon
            if severity in ["critical", "fatal"]:
                icon = QMessageBox.Icon.Critical
            elif severity == "error":
                icon = QMessageBox.Icon.Warning
            else:
                icon = QMessageBox.Icon.Information
            
            # Show dialog
            msg_box = QMessageBox(self.parent_widget)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(dialog_title)
            msg_box.setText(dialog_message)
            
            # Add buttons based on error type
            if error_record["recoverable"]:
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Ignore)
                msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
                
                # Add option to suppress this error
                if severity in ["error", "warning"]:
                    msg_box.addButton("Don't show again", QMessageBox.ButtonRole.AcceptRole)
            else:
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            
            result = msg_box.exec()
            
            # Handle dialog result
            if result == QMessageBox.StandardButton.Ignore:
                self.suppressed_errors.add(message)
            
        except Exception as e:
            self.logger.error(f"Failed to show error dialog: {e}")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def suppress_error(self, message: str):
        """Suppress future dialogs for this error message."""
        self.suppressed_errors.add(message)
    
    def clear_suppressed_errors(self):
        """Clear all suppressed errors."""
        self.suppressed_errors.clear()
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error statistics."""
        return {
            "total_errors": self.error_count,
            "total_warnings": self.warning_count,
            "recent_errors": self.error_history[-10:] if self.error_history else [],
            "suppressed_count": len(self.suppressed_errors)
        }
    
    def clear_error_history(self):
        """Clear error history."""
        self.error_history.clear()
        self.error_count = 0
        self.warning_count = 0
    
    def shutdown(self):
        """Shutdown error handler and restore original exception handler."""
        try:
            # Restore original exception handler
            sys.excepthook = self.original_excepthook
            
            # Log final statistics
            summary = self.get_error_summary()
            self.logger.info(f"Error handler shutdown. Final stats: {summary}")
            
        except Exception as e:
            self.logger.error(f"Error during error handler shutdown: {e}")


# Global error handler instance
_global_error_handler: Optional[GlobalErrorHandler] = None


def get_global_error_handler() -> Optional[GlobalErrorHandler]:
    """Get the global error handler instance."""
    return _global_error_handler


def set_global_error_handler(handler: GlobalErrorHandler):
    """Set the global error handler instance."""
    global _global_error_handler
    _global_error_handler = handler


def handle_error(
    message: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    source_component: str = "Unknown",
    exception: Optional[Exception] = None,
    show_dialog: bool = True
) -> bool:
    """Convenience function to handle errors through global handler."""
    handler = get_global_error_handler()
    if handler:
        return handler.handle_error(
            message=message,
            category=category,
            severity=severity,
            source_component=source_component,
            exception=exception,
            show_dialog=show_dialog
        )
    else:
        # Fallback to logging if no global handler
        logging.error(f"[{source_component}] {message}")
        if exception:
            logging.error(f"Exception: {exception}")
        return False


def handle_warning(
    message: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    source_component: str = "Unknown"
):
    """Convenience function to handle warnings through global handler."""
    handler = get_global_error_handler()
    if handler:
        handler.handle_warning(
            message=message,
            category=category,
            source_component=source_component
        )
    else:
        # Fallback to logging if no global handler
        logging.warning(f"[{source_component}] {message}")