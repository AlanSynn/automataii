"""Animation controls widget."""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QPushButton,
    QHBoxLayout, QLabel, QSlider, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer


class AnimationControlsWidget(QGroupBox):
    """Widget for animation playback controls.
    
    This component provides controls for playing, stopping, and
    controlling animation playback.
    """
    
    # Signals
    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    seek_requested = pyqtSignal(float)  # progress (0.0 to 1.0)
    goto_mechanism_generation = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Animation", parent)
        
        self._is_playing = False
        self._has_paths = False
        self._progress = 0.0
        
        # Timer for progress updates
        self._progress_timer = QTimer()
        self._progress_timer.timeout.connect(self._update_progress_display)
        
        self._init_ui()
        self._connect_signals()
        
        # Start with controls disabled
        self._update_button_states()
    
    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Status label
        self.status_label = QLabel("No motion paths defined")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Progress slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setToolTip("Animation progress")
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #e1e4e8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                background: #0969da;
                border-radius: 7px;
                margin: -4px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #0860ca;
            }
            QSlider::sub-page:horizontal {
                background: #0969da;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_slider)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)
        
        # Play/Pause button
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Play animation")
        self.play_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:checked {
                background-color: #2ea44f;
                color: white;
                border-color: #2c974b;
            }
            QPushButton:checked:hover {
                background-color: #2c974b;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        
        # Stop button
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setToolTip("Stop animation")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #ffebe9;
                border-color: #ff8182;
                color: #d1242f;
            }
            QPushButton:pressed {
                background-color: #ffcecb;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        
        # Reset button
        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.setToolTip("Reset animation to start")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.reset_btn)
        layout.addLayout(controls_layout)
        
        # Mechanism generation button
        self.mechanism_btn = QPushButton("Generate Mechanisms →")
        self.mechanism_btn.setToolTip("Go to Mechanism Generation tab")
        self.mechanism_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #0969da;
                border-radius: 4px;
                background-color: white;
                color: #0969da;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0969da;
                color: white;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        layout.addWidget(self.mechanism_btn)
        
        # Apply group box styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: white;
            }
        """)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.play_btn.toggled.connect(self._on_play_toggled)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.mechanism_btn.clicked.connect(self.goto_mechanism_generation.emit)
    
    def set_has_paths(self, has_paths: bool) -> None:
        """Set whether motion paths are available.
        
        Args:
            has_paths: Whether any motion paths exist
        """
        self._has_paths = has_paths
        
        if has_paths:
            self.status_label.setText("Ready to animate")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("No motion paths defined")
            self.status_label.setStyleSheet("color: #666;")
        
        self._update_button_states()
    
    def set_playing_state(self, is_playing: bool) -> None:
        """Set the playing state.
        
        Args:
            is_playing: Whether animation is playing
        """
        self._is_playing = is_playing
        self.play_btn.setChecked(is_playing)
        
        if is_playing:
            self.play_btn.setText("⏸ Pause")
            self.status_label.setText("Playing...")
            self.status_label.setStyleSheet("color: #0969da;")
            self._progress_timer.start(50)  # Update every 50ms
        else:
            self.play_btn.setText("▶ Play")
            if self._has_paths:
                self.status_label.setText("Paused")
                self.status_label.setStyleSheet("color: #fb8500;")
            self._progress_timer.stop()
        
        self._update_button_states()
    
    def set_progress(self, progress: float) -> None:
        """Set animation progress.
        
        Args:
            progress: Progress value (0.0 to 1.0)
        """
        self._progress = max(0.0, min(1.0, progress))
        
        # Update slider without triggering signal
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(int(self._progress * 100))
        self.progress_slider.blockSignals(False)
    
    def set_enabled_state(self, enabled: bool) -> None:
        """Set overall enabled state.
        
        Args:
            enabled: Whether controls should be enabled
        """
        self.setEnabled(enabled)
    
    def reset_state(self) -> None:
        """Reset to initial state."""
        self.set_playing_state(False)
        self.set_progress(0.0)
        self._has_paths = False
        self.status_label.setText("No motion paths defined")
        self.status_label.setStyleSheet("color: #666;")
        self._update_button_states()
    
    def _update_button_states(self) -> None:
        """Update button enabled states."""
        # Play button enabled when has paths
        self.play_btn.setEnabled(self._has_paths)
        
        # Stop button enabled when playing
        self.stop_btn.setEnabled(self._is_playing)
        
        # Reset button enabled when has paths and not playing
        self.reset_btn.setEnabled(self._has_paths and not self._is_playing)
        
        # Progress slider enabled when has paths
        self.progress_slider.setEnabled(self._has_paths)
        
        # Mechanism button enabled when has paths
        self.mechanism_btn.setEnabled(self._has_paths)
    
    def _update_progress_display(self) -> None:
        """Update progress display during playback."""
        # This would typically be updated by the animation service
        # For now, just show current progress
        if self._is_playing:
            percent = int(self._progress * 100)
            self.status_label.setText(f"Playing... {percent}%")
    
    def _on_play_toggled(self, checked: bool) -> None:
        """Handle play button toggle.
        
        Args:
            checked: Whether button is checked
        """
        if checked:
            self.play_requested.emit()
            logging.info("AnimationControlsWidget: Play requested")
        else:
            self.pause_requested.emit()
            logging.info("AnimationControlsWidget: Pause requested")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_requested.emit()
        logging.info("AnimationControlsWidget: Stop requested")
    
    def _on_reset_clicked(self) -> None:
        """Handle reset button click."""
        self.reset_requested.emit()
        self.set_progress(0.0)
        logging.info("AnimationControlsWidget: Reset requested")
    
    def _on_slider_moved(self, value: int) -> None:
        """Handle slider movement.
        
        Args:
            value: Slider value (0-100)
        """
        progress = value / 100.0
        self._progress = progress
        self.seek_requested.emit(progress)
        logging.debug(f"AnimationControlsWidget: Seek to {progress:.2f}")