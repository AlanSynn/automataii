"""
Skeleton settings dialog for configuring skeleton extraction options.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal

from automataii.utils.config import AppConfig
from automataii.core.models.skeleton_types import SkeletonType


class SkeletonSettingsDialog(QDialog):
    """Dialog for configuring skeleton extraction settings."""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Skeleton Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # General settings tab
        general_tab = self.create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Detection settings tab
        detection_tab = self.create_detection_tab()
        tabs.addTab(detection_tab, "Detection")
        
        # Templates tab
        templates_tab = self.create_templates_tab()
        tabs.addTab(templates_tab, "Templates")
        
        layout.addWidget(tabs)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_settings)
        
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
        
    def create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Feature toggles group
        features_group = QGroupBox("Feature Toggles")
        features_layout = QVBoxLayout(features_group)
        
        self.enable_non_human_checkbox = QCheckBox("Enable Non-Human Skeleton Support")
        self.enable_non_human_checkbox.setToolTip(
            "Enable detection and extraction of non-human skeletons "
            "(quadrupeds, birds, insects, etc.)"
        )
        features_layout.addWidget(self.enable_non_human_checkbox)
        
        self.auto_detect_checkbox = QCheckBox("Auto-Detect Skeleton Type")
        self.auto_detect_checkbox.setToolTip(
            "Automatically detect the type of skeleton from the image"
        )
        features_layout.addWidget(self.auto_detect_checkbox)
        
        self.enable_refinement_checkbox = QCheckBox("Enable Skeleton Refinement")
        self.enable_refinement_checkbox.setToolTip(
            "Enable automatic refinement of skeleton joint positions"
        )
        features_layout.addWidget(self.enable_refinement_checkbox)
        
        layout.addWidget(features_group)
        
        # Extension settings group
        extension_group = QGroupBox("Skeleton Extension")
        extension_layout = QVBoxLayout(extension_group)
        
        extension_label_layout = QHBoxLayout()
        extension_label_layout.addWidget(QLabel("Extension Factor:"))
        
        self.extension_spin = QDoubleSpinBox()
        self.extension_spin.setRange(1.0, 2.0)
        self.extension_spin.setSingleStep(0.05)
        self.extension_spin.setValue(1.1)
        self.extension_spin.setSuffix("x")
        self.extension_spin.setToolTip(
            "Factor by which to extend skeleton bones (1.1 = 10% extension)"
        )
        extension_label_layout.addWidget(self.extension_spin)
        extension_label_layout.addStretch()
        
        extension_layout.addLayout(extension_label_layout)
        layout.addWidget(extension_group)
        
        layout.addStretch()
        return widget
        
    def create_detection_tab(self) -> QWidget:
        """Create the detection settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Detection thresholds group
        thresholds_group = QGroupBox("Detection Thresholds")
        thresholds_layout = QVBoxLayout(thresholds_group)
        
        # Confidence threshold
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Confidence Threshold:"))
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.7)
        self.confidence_spin.setToolTip(
            "Minimum confidence required for skeleton type classification"
        )
        confidence_layout.addWidget(self.confidence_spin)
        confidence_layout.addStretch()
        
        thresholds_layout.addLayout(confidence_layout)
        layout.addWidget(thresholds_group)
        
        # Fallback options group
        fallback_group = QGroupBox("Fallback Options")
        fallback_layout = QVBoxLayout(fallback_group)
        
        fallback_label_layout = QHBoxLayout()
        fallback_label_layout.addWidget(QLabel("Default Skeleton Type:"))
        
        self.default_type_combo = QComboBox()
        self.default_type_combo.addItems([
            "Humanoid", "Quadruped", "Bird", "Insect", "Custom"
        ])
        self.default_type_combo.setToolTip(
            "Default skeleton type to use when detection confidence is low"
        )
        fallback_label_layout.addWidget(self.default_type_combo)
        fallback_label_layout.addStretch()
        
        fallback_layout.addLayout(fallback_label_layout)
        
        self.show_confidence_checkbox = QCheckBox("Show Detection Confidence")
        self.show_confidence_checkbox.setToolTip(
            "Display confidence scores during skeleton detection"
        )
        fallback_layout.addWidget(self.show_confidence_checkbox)
        
        layout.addWidget(fallback_group)
        layout.addStretch()
        return widget
        
    def create_templates_tab(self) -> QWidget:
        """Create the templates tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Template info
        info_label = QLabel(
            "Skeleton templates define the joint structure and default "
            "positions for different character types."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Template management group
        templates_group = QGroupBox("Template Management")
        templates_layout = QVBoxLayout(templates_group)
        
        button_layout = QHBoxLayout()
        
        self.view_templates_btn = QPushButton("View Templates")
        self.view_templates_btn.clicked.connect(self.view_templates)
        button_layout.addWidget(self.view_templates_btn)
        
        self.import_template_btn = QPushButton("Import Template")
        self.import_template_btn.clicked.connect(self.import_template)
        button_layout.addWidget(self.import_template_btn)
        
        self.export_template_btn = QPushButton("Export Template")
        self.export_template_btn.clicked.connect(self.export_template)
        button_layout.addWidget(self.export_template_btn)
        
        button_layout.addStretch()
        templates_layout.addLayout(button_layout)
        
        layout.addWidget(templates_group)
        
        # Custom skeleton builder
        custom_group = QGroupBox("Custom Skeletons")
        custom_layout = QVBoxLayout(custom_group)
        
        custom_info = QLabel(
            "Create custom skeleton structures for unique characters "
            "that don't fit standard templates."
        )
        custom_info.setWordWrap(True)
        custom_layout.addWidget(custom_info)
        
        self.open_builder_btn = QPushButton("Open Skeleton Builder")
        self.open_builder_btn.clicked.connect(self.open_skeleton_builder)
        custom_layout.addWidget(self.open_builder_btn)
        
        layout.addWidget(custom_group)
        layout.addStretch()
        return widget
        
    def load_settings(self):
        """Load current settings from AppConfig."""
        self.enable_non_human_checkbox.setChecked(
            AppConfig.ENABLE_NON_HUMAN_SKELETONS
        )
        self.auto_detect_checkbox.setChecked(
            AppConfig.AUTO_DETECT_SKELETON_TYPE
        )
        self.enable_refinement_checkbox.setChecked(
            AppConfig.ENABLE_SKELETON_REFINEMENT
        )
        self.extension_spin.setValue(
            AppConfig.SKELETON_EXTENSION_FACTOR
        )
        self.confidence_spin.setValue(
            AppConfig.SKELETON_DETECTION_CONFIDENCE_THRESHOLD
        )
        
        # Update UI state based on settings
        self.auto_detect_checkbox.setEnabled(
            self.enable_non_human_checkbox.isChecked()
        )
        self.confidence_spin.setEnabled(
            self.enable_non_human_checkbox.isChecked()
        )
        self.default_type_combo.setEnabled(
            self.enable_non_human_checkbox.isChecked()
        )
        
        # Connect state dependencies
        self.enable_non_human_checkbox.toggled.connect(
            self.on_non_human_toggled
        )
        
    def on_non_human_toggled(self, checked: bool):
        """Handle non-human skeleton toggle."""
        self.auto_detect_checkbox.setEnabled(checked)
        self.confidence_spin.setEnabled(checked)
        self.default_type_combo.setEnabled(checked)
        self.show_confidence_checkbox.setEnabled(checked)
        
    def apply_settings(self):
        """Apply the current settings."""
        # Update AppConfig
        AppConfig.ENABLE_NON_HUMAN_SKELETONS = (
            self.enable_non_human_checkbox.isChecked()
        )
        AppConfig.AUTO_DETECT_SKELETON_TYPE = (
            self.auto_detect_checkbox.isChecked()
        )
        AppConfig.ENABLE_SKELETON_REFINEMENT = (
            self.enable_refinement_checkbox.isChecked()
        )
        AppConfig.SKELETON_EXTENSION_FACTOR = self.extension_spin.value()
        AppConfig.SKELETON_DETECTION_CONFIDENCE_THRESHOLD = (
            self.confidence_spin.value()
        )
        
        # Save settings to file
        AppConfig.save_settings()
        
        # Emit signal
        self.settings_changed.emit()
        
        # Accept dialog
        self.accept()
        
    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.enable_non_human_checkbox.setChecked(False)
        self.auto_detect_checkbox.setChecked(True)
        self.enable_refinement_checkbox.setChecked(True)
        self.extension_spin.setValue(1.1)
        self.confidence_spin.setValue(0.7)
        self.default_type_combo.setCurrentIndex(0)
        self.show_confidence_checkbox.setChecked(False)
        
    def view_templates(self):
        """Open template viewer dialog."""
        from automataii.gui.dialogs.template_selection_dialog import TemplateSelectionDialog
        dialog = TemplateSelectionDialog(self)
        dialog.exec_()
        
    def import_template(self):
        """Import a skeleton template from file."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Skeleton Template", "", "JSON Files (*.json)"
        )
        
        if filename:
            # TODO: Implement template import
            QMessageBox.information(
                self, "Import Template",
                "Template import functionality will be implemented soon."
            )
            
    def export_template(self):
        """Export a skeleton template to file."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Skeleton Template", "", "JSON Files (*.json)"
        )
        
        if filename:
            # TODO: Implement template export
            QMessageBox.information(
                self, "Export Template",
                "Template export functionality will be implemented soon."
            )
            
    def open_skeleton_builder(self):
        """Open the custom skeleton builder dialog."""
        from automataii.gui.dialogs.custom_skeleton_dialog import CustomSkeletonDialog
        
        dialog = CustomSkeletonDialog(self)
        if dialog.exec_():
            # Handle the created skeleton
            skeleton = dialog.skeleton_created
            if skeleton:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Skeleton Created",
                    "Custom skeleton has been created successfully."
                )