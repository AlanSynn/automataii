import sys
import time
import logging
import cv2
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QMessageBox,
    QStyle,
)
from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot


class CameraWorker(QObject):
    """Worker thread to capture frames from the camera without blocking the GUI."""

    frameCaptured = pyqtSignal(object)  # Emits numpy array (BGR frame)
    errorOccurred = pyqtSignal(str)

    def __init__(self, camera_index=0):
        super().__init__()
        self._camera_index = camera_index
        self._running = False
        self._cap = None

    def run(self):
        """Starts capturing frames."""
        logging.info(f"CameraWorker starting on thread {QThread.currentThreadId()}")
        self._running = True
        try:
            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                self.errorOccurred.emit(
                    f"Failed to open camera index {self._camera_index}."
                )
                self._running = False
                return

            logging.info(f"Camera {self._camera_index} opened successfully.")
            while self._running:
                ret, frame = self._cap.read()
                if ret:
                    self.frameCaptured.emit(frame)
                    # Slight delay to avoid overwhelming the GUI thread
                    # Adjust based on performance
                    QThread.msleep(30)  # ~33 FPS target
                else:
                    logging.warning("Failed to capture frame.")
                    # Optionally emit an error or just stop?
                    # self.errorOccurred.emit("Failed to capture frame.")
                    QThread.msleep(100)  # Wait a bit before retrying?

        except Exception as e:
            logging.error(f"Camera error: {e}", exc_info=True)
            self.errorOccurred.emit(f"Camera runtime error: {e}")
        finally:
            if self._cap and self._cap.isOpened():
                self._cap.release()
                logging.info(f"Camera {self._camera_index} released.")
            self._cap = None
        logging.info(f"CameraWorker finished on thread {QThread.currentThreadId()}")

    def stop(self):
        """Signals the worker to stop capturing."""
        logging.info("CameraWorker stop requested.")
        self._running = False


class CameraDialog(QDialog):
    """Dialog window for camera preview and image capture."""

    def __init__(self, parent=None, camera_index=0):
        super().__init__(parent)
        self.setWindowTitle("Camera Capture")
        self.setModal(True)
        self.resize(800, 600)

        self._thread = None
        self._worker = None
        self._camera_index = camera_index
        self.captured_image = None  # Stores the captured frame (numpy array BGR)
        self._scene_pixmap_item = None
        self._current_frame = None  # Store the latest frame for capture

        self._setup_ui()
        self._setup_camera()

    def _setup_ui(self):
        """Creates the UI elements for the dialog."""
        layout = QVBoxLayout(self)

        # Graphics View for preview
        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._view)

        # Status Label
        self._status_label = QLabel("Initializing camera...")
        layout.addWidget(self._status_label)

        # Buttons
        style = self.style()
        button_layout = QHBoxLayout()
        self._capture_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOkButton), "Capture"
        )
        self._capture_btn.clicked.connect(self._capture_and_accept)
        self._capture_btn.setEnabled(False)  # Disabled until first frame
        self._cancel_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton), "Cancel"
        )
        self._cancel_btn.clicked.connect(self.reject)  # Reject closes the dialog
        button_layout.addStretch()
        button_layout.addWidget(self._capture_btn)
        button_layout.addWidget(self._cancel_btn)
        layout.addLayout(button_layout)

    def _setup_camera(self):
        """Initializes the camera worker and thread."""
        self._thread = QThread()
        self._worker = CameraWorker(self._camera_index)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._worker.frameCaptured.connect(self._update_preview)
        self._worker.errorOccurred.connect(self._handle_camera_error)
        self._thread.started.connect(self._worker.run)
        # Ensure cleanup when thread finishes
        self._thread.finished.connect(self._thread.deleteLater)
        # Connect the worker's deletion to the thread's finished signal
        self._thread.finished.connect(self._worker.deleteLater)

        self._thread.start()
        logging.info("Camera worker thread started.")

    @pyqtSlot(object)
    def _update_preview(self, frame):
        """Updates the QGraphicsView with the latest frame from the worker."""
        if not self._capture_btn.isEnabled():
            self._capture_btn.setEnabled(True)
            self._status_label.setText("Camera Ready")
            self._status_label.setStyleSheet("color: lightgreen;")

        try:
            # Convert BGR frame to RGB QImage
            self._current_frame = frame  # Keep BGR frame for capture
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
            )
            pixmap = QPixmap.fromImage(qt_image)

            if self._scene_pixmap_item is None:
                self._scene_pixmap_item = QGraphicsPixmapItem(pixmap)
                self._scene.addItem(self._scene_pixmap_item)
                self._view.fitInView(
                    self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
                )
            else:
                self._scene_pixmap_item.setPixmap(pixmap)

        except Exception as e:
            logging.error(f"Error updating preview: {e}", exc_info=True)
            # Optionally disable capture or show error in status

    @pyqtSlot(str)
    def _handle_camera_error(self, error_message):
        """Displays an error message if the camera worker fails."""
        logging.error(f"Camera Error: {error_message}")
        self._status_label.setText(f"Error: {error_message}")
        self._status_label.setStyleSheet("color: red;")
        self._capture_btn.setEnabled(False)
        QMessageBox.critical(self, "Camera Error", error_message)
        # Consider stopping the worker/thread here if the error is fatal
        self.stop_camera()

    def _capture_and_accept(self):
        """Stores the current frame and accepts the dialog."""
        if self._current_frame is not None:
            self.captured_image = self._current_frame.copy()  # Store the BGR frame
            logging.info("Image captured.")
            self.accept()  # Close dialog with Accepted state
        else:
            logging.warning("Capture button clicked, but no frame available.")
            QMessageBox.warning(self, "Capture Error", "No frame available to capture.")

    def stop_camera(self):
        """Stops the camera worker thread safely."""
        logging.info("Stopping camera...")
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(1000):  # Wait 1 sec
                logging.warning("Camera thread did not quit gracefully, terminating.")
                self._thread.terminate()
                self._thread.wait()  # Wait for termination
        self._thread = None
        self._worker = None
        logging.info("Camera stopped.")

    def resizeEvent(self, event):
        """Ensures the preview fits the view on resize."""
        super().resizeEvent(event)
        if self._scene_pixmap_item:
            self._view.fitInView(
                self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def closeEvent(self, event):
        """Ensures camera is stopped when the dialog is closed."""
        self.stop_camera()
        super().closeEvent(event)

    # Override reject to ensure camera stops
    def reject(self):
        self.stop_camera()
        super().reject()

    # Override accept to ensure camera stops
    def accept(self):
        self.stop_camera()
        super().accept()


# Example Usage (for testing the dialog directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    dialog = CameraDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        print("Image captured successfully!")
        if dialog.captured_image is not None:
            print(f"Captured frame shape: {dialog.captured_image.shape}")
            # Optionally save or display the image here
            # cv2.imwrite("captured_test.png", dialog.captured_image)
            # cv2.imshow("Captured Image", dialog.captured_image)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()
        else:
            print("Dialog accepted but no image was captured.")
    else:
        print("Camera dialog cancelled.")
    sys.exit()
