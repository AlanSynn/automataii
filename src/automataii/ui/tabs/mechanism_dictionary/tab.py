"""
Main Mechanism Dictionary tab implementation.
Orchestrates all components for mechanism browsing and exploration.
"""

import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QGraphicsView, QMessageBox

from automataii.ui.tabs.base.tab import BaseTab
from .state_manager import MechanismDictionaryStateManager
from .ui_panel import MechanismDictionaryUIPanel
from .preview_manager import MechanismPreviewManager

logger = logging.getLogger(__name__)


class MechanismDictionaryTab(BaseTab):
    """
    Mechanism Dictionary tab for browsing and exploring mechanisms.
    
    Features:
    - Categorized mechanism browsing
    - Interactive parameter adjustment
    - Real-time animation preview
    - Search and filtering
    - Detailed mechanism information
    """
    
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        
        # Core components
        self.state_manager: Optional[MechanismDictionaryStateManager] = None
        self.ui_panel: Optional[MechanismDictionaryUIPanel] = None
        self.preview_manager: Optional[MechanismPreviewManager] = None
        self.graphics_view: Optional[QGraphicsView] = None
        
        # Initialize the tab
        self._initialize_tab()
        
        logger.info("MechanismDictionaryTab initialized")
    
    def _initialize_tab(self):
        """Initialize the tab components."""
        try:
            # Setup UI
            self._setup_ui()
            
            # Initialize state manager
            self.state_manager = MechanismDictionaryStateManager(self)
            
            # Initialize preview manager
            self.preview_manager = MechanismPreviewManager(self.graphics_view, self)
            
            # Connect signals
            self._connect_signals()
            
            # Load initial data
            self._load_initial_data()
            
        except Exception as e:
            logger.error(f"Failed to initialize MechanismDictionaryTab: {e}")
            self._show_error("Failed to initialize Mechanism Dictionary", str(e))
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main layout
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # Create main splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout().addWidget(self.main_splitter)
        
        # Create UI panel (sidebar + parameters)
        self.ui_panel = MechanismDictionaryUIPanel()
        self.main_splitter.addWidget(self.ui_panel)
        
        # Create preview area
        self.graphics_view = QGraphicsView()
        self.graphics_view.setMinimumWidth(400)
        self.main_splitter.addWidget(self.graphics_view)
        
        # Set splitter proportions (ui_panel:preview = 1:2)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([300, 600])
    
    def _connect_signals(self):
        """Connect all component signals."""
        if not all([self.state_manager, self.ui_panel, self.preview_manager]):
            return
        
        # State manager signals
        self.state_manager.category_changed.connect(self._on_category_changed)
        self.state_manager.mechanism_changed.connect(self._on_mechanism_changed)
        self.state_manager.parameter_changed.connect(self._on_parameter_changed)
        self.state_manager.animation_state_changed.connect(self._on_animation_state_changed)
        
        # UI panel signals
        self.ui_panel.category_selected.connect(self.state_manager.set_current_category)
        self.ui_panel.mechanism_selected.connect(self.state_manager.set_current_mechanism)
        self.ui_panel.search_query_changed.connect(self.state_manager.set_search_query)
        self.ui_panel.parameter_changed.connect(self.state_manager.set_mechanism_parameter)
        
        # Animation control signals
        self.ui_panel.animation_play_requested.connect(self.state_manager.start_animation)
        self.ui_panel.animation_stop_requested.connect(self.state_manager.stop_animation)
        self.ui_panel.animation_reset_requested.connect(self.state_manager.reset_animation)
        self.ui_panel.animation_speed_changed.connect(self.state_manager.set_animation_speed)
        
        # Preview manager signals (for future use)
        self.preview_manager.mechanism_loaded.connect(self._on_mechanism_loaded)
        self.preview_manager.animation_started.connect(self._on_preview_animation_started)
        self.preview_manager.animation_stopped.connect(self._on_preview_animation_stopped)
    
    def _load_initial_data(self):
        """Load initial data into the UI."""
        if not all([self.state_manager, self.ui_panel]):
            return
        
        try:
            # Load categories into UI
            categories = self.state_manager.get_categories()
            self.ui_panel.load_categories(categories)
            
            # Set initial mechanism if available
            current_mechanism_info = self.state_manager.get_current_mechanism_info()
            if current_mechanism_info:
                self.ui_panel.set_current_mechanism(current_mechanism_info)
                
                # Load mechanism into preview
                mechanism_instance = self.state_manager.get_current_mechanism_instance()
                if mechanism_instance:
                    self.preview_manager.load_mechanism(mechanism_instance)
            
            logger.debug(f"Loaded {len(categories)} categories with mechanisms")
            
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")
            self._show_error("Failed to load mechanism data", str(e))
    
    # Event handlers
    def _on_category_changed(self, category_id: str):
        """Handle category selection changes."""
        logger.debug(f"Category changed to: {category_id}")
        # Category changes are handled automatically by the tree view
    
    def _on_mechanism_changed(self, mechanism_id: str):
        """Handle mechanism selection changes."""
        if not all([self.state_manager, self.ui_panel, self.preview_manager]):
            return
        
        try:
            # Update UI panel
            mechanism_info = self.state_manager.get_current_mechanism_info()
            self.ui_panel.set_current_mechanism(mechanism_info)
            
            # Load mechanism into preview
            mechanism_instance = self.state_manager.get_current_mechanism_instance()
            if mechanism_instance:
                self.preview_manager.load_mechanism(mechanism_instance)
                logger.debug(f"Loaded mechanism: {mechanism_id}")
            else:
                self.preview_manager.clear_mechanism()
                logger.warning(f"Failed to create mechanism instance: {mechanism_id}")
                
        except Exception as e:
            logger.error(f"Failed to change mechanism: {e}")
            self._show_error("Failed to load mechanism", str(e))
    
    def _on_parameter_changed(self, parameter_name: str, value):
        """Handle parameter value changes."""
        if self.ui_panel:
            # Update UI to reflect the change
            self.ui_panel.update_parameter_value(parameter_name, value)
        
        logger.debug(f"Parameter {parameter_name} changed to: {value}")
    
    def _on_animation_state_changed(self, is_animating: bool):
        """Handle animation state changes."""
        if self.ui_panel:
            self.ui_panel.set_animation_state(is_animating)
        
        # Sync preview manager animation state
        if self.preview_manager:
            if is_animating:
                self.preview_manager.start_animation()
            else:
                self.preview_manager.stop_animation()
        
        logger.debug(f"Animation state changed: {'playing' if is_animating else 'stopped'}")
    
    def _on_mechanism_loaded(self, mechanism_id: str):
        """Handle successful mechanism loading in preview."""
        logger.debug(f"Mechanism loaded in preview: {mechanism_id}")
    
    def _on_preview_animation_started(self):
        """Handle animation start in preview."""
        logger.debug("Preview animation started")
    
    def _on_preview_animation_stopped(self):
        """Handle animation stop in preview."""
        logger.debug("Preview animation stopped")
    
    # BaseTab interface implementation
    def activate_tab(self):
        """Called when tab becomes active."""
        logger.debug("Mechanism Dictionary tab activated")
        # Refresh preview if needed
        if self.preview_manager and self.state_manager:
            mechanism_instance = self.state_manager.get_current_mechanism_instance()
            if mechanism_instance and not self.preview_manager.current_mechanism:
                self.preview_manager.load_mechanism(mechanism_instance)
    
    def deactivate_tab(self):
        """Called when tab becomes inactive."""
        logger.debug("Mechanism Dictionary tab deactivated")
        # Stop animation to save resources
        if self.state_manager and self.state_manager.is_animating():
            self.state_manager.stop_animation()
    
    def cleanup(self):
        """Cleanup resources when tab is closed."""
        logger.debug("Cleaning up Mechanism Dictionary tab")
        
        # Stop any running animations
        if self.state_manager and self.state_manager.is_animating():
            self.state_manager.stop_animation()
        
        # Clear preview
        if self.preview_manager:
            self.preview_manager.clear_mechanism()
        
        # Disconnect signals
        if self.state_manager:
            self.state_manager.deleteLater()
        
        super().cleanup()
    
    # Utility methods
    def _show_error(self, title: str, message: str):
        """Show an error message to the user."""
        QMessageBox.critical(self, title, message)
    
    def get_current_mechanism_id(self) -> Optional[str]:
        """Get the currently selected mechanism ID."""
        if self.state_manager:
            return self.state_manager.get_current_mechanism_id()
        return None
    
    def get_mechanism_count(self) -> int:
        """Get the total number of mechanisms."""
        if self.state_manager:
            return self.state_manager.get_mechanism_count()
        return 0
    
    def reload_catalog(self) -> bool:
        """Reload the mechanism catalog."""
        if self.state_manager:
            success = self.state_manager.reload_catalog()
            if success and self.ui_panel:
                # Reload UI
                categories = self.state_manager.get_categories()
                self.ui_panel.load_categories(categories)
            return success
        return False
    
    def export_current_mechanism(self) -> bool:
        """Export the current mechanism (placeholder for future implementation)."""
        logger.info("Mechanism export not yet implemented")
        return False
    
    def take_screenshot(self) -> bool:
        """Take a screenshot of the current preview."""
        if self.preview_manager:
            try:
                pixmap = self.preview_manager.take_snapshot()
                # Could save or copy to clipboard
                logger.info("Screenshot taken")
                return True
            except Exception as e:
                logger.error(f"Failed to take screenshot: {e}")
        return False