"""
Catalog manager for mechanism dictionary.
Loads and manages the mechanism catalog with caching support.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MechanismInfo:
    """Information about a mechanism from the catalog."""
    
    id: str
    name: str
    description: str
    type: str
    class_name: str
    category: str
    tags: List[str]
    complexity: str
    parameters: Dict[str, Any]
    preview_size: List[int]
    animation_duration: int


@dataclass
class CategoryInfo:
    """Information about a mechanism category."""
    
    id: str
    name: str
    description: str
    icon: str
    mechanisms: List[MechanismInfo]


class CatalogManager:
    """
    Manages the mechanism catalog with caching and search functionality.
    """
    
    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or self._get_default_catalog_path()
        self._catalog_data: Optional[Dict] = None
        self._categories: Dict[str, CategoryInfo] = {}
        self._mechanisms: Dict[str, MechanismInfo] = {}
        self._search_tags: List[str] = []
        
        # Load catalog on initialization
        self.load_catalog()
    
    def _get_default_catalog_path(self) -> Path:
        """Get the default path to the mechanism catalog."""
        # Assuming the catalog is in config/mechanism_catalog.json relative to project root
        current_dir = Path(__file__).parent  # mechanisms/
        project_root = current_dir.parent.parent.parent.parent.parent  # Go up 5 levels to project root
        return project_root / "config" / "mechanism_catalog.json"
    
    def load_catalog(self) -> bool:
        """
        Load the mechanism catalog from JSON file.
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            if not self.catalog_path.exists():
                logger.error(f"Catalog file not found: {self.catalog_path}")
                return False
            
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                self._catalog_data = json.load(f)
            
            self._parse_catalog()
            logger.info(f"Loaded mechanism catalog with {len(self._categories)} categories and {len(self._mechanisms)} mechanisms")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load catalog: {e}")
            return False
    
    def _parse_catalog(self):
        """Parse the loaded catalog data into structured objects."""
        if not self._catalog_data:
            return
            
        # Parse search tags
        self._search_tags = self._catalog_data.get("search_tags", [])
        
        # Parse categories and mechanisms
        categories_data = self._catalog_data.get("categories", {})
        
        for category_id, category_data in categories_data.items():
            mechanisms = []
            
            # Parse mechanisms in this category
            for mechanism_id, mechanism_data in category_data.get("mechanisms", {}).items():
                mechanism_info = MechanismInfo(
                    id=mechanism_id,
                    name=mechanism_data.get("name", "Unknown"),
                    description=mechanism_data.get("description", ""),
                    type=mechanism_data.get("type", ""),
                    class_name=mechanism_data.get("class", ""),
                    category=category_id,
                    tags=mechanism_data.get("tags", []),
                    complexity=mechanism_data.get("complexity", "unknown"),
                    parameters=mechanism_data.get("parameters", {}),
                    preview_size=mechanism_data.get("preview_size", [300, 200]),
                    animation_duration=mechanism_data.get("animation_duration", 2000)
                )
                
                mechanisms.append(mechanism_info)
                self._mechanisms[mechanism_id] = mechanism_info
            
            # Create category info
            category_info = CategoryInfo(
                id=category_id,
                name=category_data.get("name", "Unknown Category"),
                description=category_data.get("description", ""),
                icon=category_data.get("icon", "🔧"),
                mechanisms=mechanisms
            )
            
            self._categories[category_id] = category_info
    
    def get_categories(self) -> List[CategoryInfo]:
        """Get all categories."""
        return list(self._categories.values())
    
    def get_category(self, category_id: str) -> Optional[CategoryInfo]:
        """Get a specific category by ID."""
        return self._categories.get(category_id)
    
    def get_mechanisms(self) -> List[MechanismInfo]:
        """Get all mechanisms."""
        return list(self._mechanisms.values())
    
    def get_mechanism(self, mechanism_id: str) -> Optional[MechanismInfo]:
        """Get a specific mechanism by ID."""
        return self._mechanisms.get(mechanism_id)
    
    def get_mechanisms_by_category(self, category_id: str) -> List[MechanismInfo]:
        """Get all mechanisms in a specific category."""
        category = self._categories.get(category_id)
        return category.mechanisms if category else []
    
    def search_mechanisms(self, query: str, category_filter: Optional[str] = None, 
                         tag_filter: Optional[List[str]] = None,
                         complexity_filter: Optional[str] = None) -> List[MechanismInfo]:
        """
        Search mechanisms by various criteria.
        
        Args:
            query: Text to search in name and description
            category_filter: Limit to specific category
            tag_filter: Limit to mechanisms with these tags
            complexity_filter: Limit to specific complexity level
            
        Returns:
            List of matching mechanisms
        """
        results = []
        query_lower = query.lower() if query else ""
        
        for mechanism in self._mechanisms.values():
            # Category filter
            if category_filter and mechanism.category != category_filter:
                continue
            
            # Complexity filter
            if complexity_filter and mechanism.complexity != complexity_filter:
                continue
            
            # Tag filter
            if tag_filter and not any(tag in mechanism.tags for tag in tag_filter):
                continue
            
            # Text search
            if query_lower:
                searchable_text = f"{mechanism.name} {mechanism.description} {' '.join(mechanism.tags)}".lower()
                if query_lower not in searchable_text:
                    continue
            
            results.append(mechanism)
        
        return results
    
    def get_search_tags(self) -> List[str]:
        """Get all available search tags."""
        return self._search_tags.copy()
    
    def get_complexity_levels(self) -> List[str]:
        """Get all complexity levels in the catalog."""
        levels = set()
        for mechanism in self._mechanisms.values():
            levels.add(mechanism.complexity)
        return sorted(list(levels))
    
    def reload_catalog(self) -> bool:
        """Reload the catalog from file."""
        self._catalog_data = None
        self._categories.clear()
        self._mechanisms.clear()
        self._search_tags.clear()
        return self.load_catalog()
    
    def get_mechanism_count(self) -> int:
        """Get total number of mechanisms."""
        return len(self._mechanisms)
    
    def get_category_count(self) -> int:
        """Get total number of categories."""
        return len(self._categories)