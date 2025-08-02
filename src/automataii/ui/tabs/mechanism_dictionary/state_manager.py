"""
State manager for the Mechanism Dictionary tab.
Manages the current selection, parameters, and animation state.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal

from automataii.domain.fabrication.mechanisms import CatalogManager, BaseMechanism
from automataii.domain.fabrication.mechanisms.catalog_manager import MechanismInfo, CategoryInfo

logger = logging.getLogger(__name__)


class MechanismDictionaryStateManager(QObject):
    """
    Manages the state of the Mechanism Dictionary tab.
    
    Tracks:
    - Current selected category and mechanism
    - Active mechanism instance and its parameters
    - Animation state
    - Search and filter settings
    """
    
    # Signals
    category_changed = pyqtSignal(str)  # category_id
    mechanism_changed = pyqtSignal(str)  # mechanism_id
    parameter_changed = pyqtSignal(str, object)  # parameter_name, value
    animation_state_changed = pyqtSignal(bool)  # is_animating
    search_query_changed = pyqtSignal(str)  # query
    filter_changed = pyqtSignal(dict)  # filters
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Core components
        self.catalog_manager = CatalogManager()
        
        # Current state
        self._current_category_id: Optional[str] = None
        self._current_mechanism_id: Optional[str] = None
        self._current_mechanism_instance: Optional[BaseMechanism] = None
        
        # Search and filter state
        self._search_query: str = ""
        self._category_filter: Optional[str] = None
        self._tag_filter: Optional[list] = None
        self._complexity_filter: Optional[str] = None
        
        # Animation state
        self._is_animating: bool = False
        self._animation_speed: float = 1.0
        
        # UI state
        self._sidebar_expanded: bool = True
        self._preview_scale: float = 1.0
        
        # Initialize with first category/mechanism if available
        self._initialize_default_selection()
    
    def _initialize_default_selection(self):
        """Initialize with the first available category and mechanism."""
        categories = self.catalog_manager.get_categories()
        if categories:
            first_category = categories[0]
            self.set_current_category(first_category.id)
            
            if first_category.mechanisms:
                self.set_current_mechanism(first_category.mechanisms[0].id)
    
    # Category management
    def get_categories(self) -> list[CategoryInfo]:
        """Get all available categories."""
        return self.catalog_manager.get_categories()
    
    def get_current_category_id(self) -> Optional[str]:
        """Get the currently selected category ID."""
        return self._current_category_id
    
    def get_current_category(self) -> Optional[CategoryInfo]:
        """Get the currently selected category."""
        if self._current_category_id:
            return self.catalog_manager.get_category(self._current_category_id)
        return None
    
    def set_current_category(self, category_id: str):
        """Set the current category."""
        if category_id != self._current_category_id:
            self._current_category_id = category_id
            self.category_changed.emit(category_id)
            logger.debug(f"Category changed to: {category_id}")
    
    # Mechanism management
    def get_mechanisms(self, category_id: Optional[str] = None) -> list[MechanismInfo]:
        """Get mechanisms, optionally filtered by category."""
        if category_id:
            return self.catalog_manager.get_mechanisms_by_category(category_id)
        return self.catalog_manager.get_mechanisms()
    
    def get_current_mechanism_id(self) -> Optional[str]:
        """Get the currently selected mechanism ID."""
        return self._current_mechanism_id
    
    def get_current_mechanism_info(self) -> Optional[MechanismInfo]:
        """Get the currently selected mechanism info."""
        if self._current_mechanism_id:
            return self.catalog_manager.get_mechanism(self._current_mechanism_id)
        return None
    
    def get_current_mechanism_instance(self) -> Optional[BaseMechanism]:
        """Get the current mechanism instance."""
        return self._current_mechanism_instance
    
    def set_current_mechanism(self, mechanism_id: str):
        """Set the current mechanism and create its instance."""
        if mechanism_id != self._current_mechanism_id:
            self._current_mechanism_id = mechanism_id
            self._create_mechanism_instance(mechanism_id)
            self.mechanism_changed.emit(mechanism_id)
            logger.debug(f"Mechanism changed to: {mechanism_id}")
    
    def _create_mechanism_instance(self, mechanism_id: str):
        """Create an instance of the specified mechanism."""
        mechanism_info = self.catalog_manager.get_mechanism(mechanism_id)
        if not mechanism_info:
            logger.error(f"Mechanism not found: {mechanism_id}")
            return
        
        try:
            # Stop current animation if running
            if self._current_mechanism_instance:
                self._current_mechanism_instance.stop_animation()
            
            # Extract default parameters from catalog
            default_params = {}
            for param_name, param_info in mechanism_info.parameters.items():
                default_params[param_name] = param_info.get("default", 0.0)
            
            # Import and create the mechanism class based on class name
            mechanism_instance = None
            
            if mechanism_info.class_name == "FourBarLinkage":
                from automataii.domain.fabrication.mechanisms.four_bar_linkage import FourBarLinkage
                mechanism_instance = FourBarLinkage(mechanism_id, default_params)
                
            elif mechanism_info.class_name == "CamFollower":
                from automataii.domain.fabrication.mechanisms.cam_follower import CamFollower
                mechanism_instance = CamFollower(mechanism_id, default_params)
                
            elif mechanism_info.class_name == "SimpleGearTrain":
                from automataii.domain.fabrication.mechanisms.simple_gear_train import SimpleGearTrain
                mechanism_instance = SimpleGearTrain(mechanism_id, default_params)
                
            elif mechanism_info.class_name == "PlanetaryGear":
                from automataii.domain.fabrication.mechanisms.planetary_gear import PlanetaryGear
                mechanism_instance = PlanetaryGear(mechanism_id, default_params)
                
            elif mechanism_info.class_name == "GenevaDrive":
                from automataii.domain.fabrication.mechanisms.geneva_drive import GenevaDrive
                mechanism_instance = GenevaDrive(mechanism_id, default_params)
                
            else:
                logger.warning(f"Mechanism class not implemented: {mechanism_info.class_name}")
                self._current_mechanism_instance = None
                return
            
            # Set the created instance
            self._current_mechanism_instance = mechanism_instance
            
            # Connect signals
            self._current_mechanism_instance.parameter_changed.connect(self._on_mechanism_parameter_changed)
            
            logger.info(f"Created {mechanism_info.class_name} instance")
                
        except Exception as e:
            logger.error(f"Failed to create mechanism instance: {e}")
            self._current_mechanism_instance = None
    
    def _on_mechanism_parameter_changed(self, parameter_name: str, value):
        """Handle parameter changes from the mechanism instance."""
        self.parameter_changed.emit(parameter_name, value)
    
    # Parameter management
    def get_mechanism_parameters(self) -> Dict[str, Any]:
        """Get the current mechanism's parameters."""
        if self._current_mechanism_instance:
            return self._current_mechanism_instance.parameters.copy()
        return {}
    
    def set_mechanism_parameter(self, parameter_name: str, value: Any):
        """Set a mechanism parameter."""
        if self._current_mechanism_instance:
            self._current_mechanism_instance.set_parameter(parameter_name, value)
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get parameter information for the current mechanism."""
        if self._current_mechanism_instance:
            return self._current_mechanism_instance.get_parameter_info()
        return {}
    
    # Animation management
    def is_animating(self) -> bool:
        """Check if animation is currently running."""
        return self._is_animating
    
    def start_animation(self):
        """Start mechanism animation."""
        if self._current_mechanism_instance and not self._is_animating:
            self._current_mechanism_instance.start_animation()
            self._is_animating = True
            self.animation_state_changed.emit(True)
            logger.debug("Animation started")
    
    def stop_animation(self):
        """Stop mechanism animation."""
        if self._current_mechanism_instance and self._is_animating:
            self._current_mechanism_instance.stop_animation()
            self._is_animating = False
            self.animation_state_changed.emit(False)
            logger.debug("Animation stopped")
    
    def reset_animation(self):
        """Reset animation to beginning."""
        if self._current_mechanism_instance:
            self._current_mechanism_instance.reset_animation()
            logger.debug("Animation reset")
    
    def get_animation_speed(self) -> float:
        """Get the current animation speed."""
        return self._animation_speed
    
    def set_animation_speed(self, speed: float):
        """Set the animation speed."""
        self._animation_speed = max(0.1, min(5.0, speed))
        if self._current_mechanism_instance:
            self._current_mechanism_instance.set_animation_speed(self._animation_speed)
    
    # Search and filtering
    def get_search_query(self) -> str:
        """Get the current search query."""
        return self._search_query
    
    def set_search_query(self, query: str):
        """Set the search query."""
        if query != self._search_query:
            self._search_query = query
            self.search_query_changed.emit(query)
    
    def get_filters(self) -> Dict[str, Any]:
        """Get current filter settings."""
        return {
            "category": self._category_filter,
            "tags": self._tag_filter,
            "complexity": self._complexity_filter
        }
    
    def set_category_filter(self, category_id: Optional[str]):
        """Set category filter."""
        if category_id != self._category_filter:
            self._category_filter = category_id
            self.filter_changed.emit(self.get_filters())
    
    def set_tag_filter(self, tags: Optional[list]):
        """Set tag filter."""
        if tags != self._tag_filter:
            self._tag_filter = tags
            self.filter_changed.emit(self.get_filters())
    
    def set_complexity_filter(self, complexity: Optional[str]):
        """Set complexity filter."""
        if complexity != self._complexity_filter:
            self._complexity_filter = complexity
            self.filter_changed.emit(self.get_filters())
    
    def clear_filters(self):
        """Clear all filters."""
        self._category_filter = None
        self._tag_filter = None
        self._complexity_filter = None
        self.filter_changed.emit(self.get_filters())
    
    def search_mechanisms(self) -> list[MechanismInfo]:
        """Search mechanisms based on current query and filters."""
        return self.catalog_manager.search_mechanisms(
            query=self._search_query,
            category_filter=self._category_filter,
            tag_filter=self._tag_filter,
            complexity_filter=self._complexity_filter
        )
    
    # UI state
    def is_sidebar_expanded(self) -> bool:
        """Check if sidebar is expanded."""
        return self._sidebar_expanded
    
    def set_sidebar_expanded(self, expanded: bool):
        """Set sidebar expansion state."""
        self._sidebar_expanded = expanded
    
    def get_preview_scale(self) -> float:
        """Get preview scale factor."""
        return self._preview_scale
    
    def set_preview_scale(self, scale: float):
        """Set preview scale factor."""
        self._preview_scale = max(0.1, min(3.0, scale))
    
    # Utility methods
    def reload_catalog(self) -> bool:
        """Reload the mechanism catalog."""
        success = self.catalog_manager.reload_catalog()
        if success:
            self._initialize_default_selection()
        return success
    
    def get_mechanism_count(self) -> int:
        """Get total number of mechanisms."""
        return self.catalog_manager.get_mechanism_count()
    
    def get_category_count(self) -> int:
        """Get total number of categories."""
        return self.catalog_manager.get_category_count()