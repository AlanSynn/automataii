"""
Central factory for mechanism-specific parametric editing.

Provides a unified interface for creating and managing parametric editors
for different mechanism types. Follows the same pattern as visual_factory.py.
"""

import logging

from .base.parametric_interface import ParametricMechanismInterface

logger = logging.getLogger(__name__)


class ParametricFactory:
    """
    Central factory for creating mechanism-specific parametric editors.

    Maintains a registry of mechanism types and their corresponding
    parametric editor implementations.
    """

    # Registry of mechanism types to their parametric editor classes
    _registry: dict[str, type[ParametricMechanismInterface]] = {}

    @classmethod
    def register_mechanism(
        cls, mechanism_type: str, parametric_class: type[ParametricMechanismInterface]
    ) -> None:
        """
        Register a mechanism type with its parametric editor class.

        Args:
            mechanism_type: Mechanism type identifier (e.g., '4_bar_linkage')
            parametric_class: Class implementing ParametricMechanismInterface
        """
        cls._registry[mechanism_type] = parametric_class
        logger.debug(f"Registered parametric editor for {mechanism_type}")

    @classmethod
    def create_parametric_editor(
        cls, mechanism_id: str, layer_data: dict, scene_manager
    ) -> ParametricMechanismInterface | None:
        """
        Create a parametric editor for the specified mechanism.

        Args:
            mechanism_id: Unique mechanism identifier
            layer_data: Mechanism data from state manager
            scene_manager: Scene manager for adding/removing handles

        Returns:
            ParametricMechanismInterface implementation or None if not supported
        """
        mech_type = layer_data.get("type")
        original_json_type = layer_data.get("original_json_type", mech_type)

        # Normalize mechanism type for lookup
        normalized_type = cls._normalize_mechanism_type(mech_type, original_json_type)

        if normalized_type in cls._registry:
            parametric_class = cls._registry[normalized_type]
            try:
                editor = parametric_class(mechanism_id, layer_data, scene_manager)
                logger.debug(f"Created parametric editor for {normalized_type}")
                return editor
            except Exception as e:
                logger.error(f"Failed to create parametric editor for {normalized_type}: {e}")
                return None
        else:
            logger.warning(f"No parametric editor registered for mechanism type: {normalized_type}")
            return None

    @classmethod
    def get_supported_mechanisms(cls) -> list[str]:
        """Get list of mechanism types that support parametric editing."""
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, layer_data: dict) -> bool:
        """Check if a mechanism supports parametric editing."""
        mech_type = layer_data.get("type")
        original_json_type = layer_data.get("original_json_type", mech_type)
        normalized_type = cls._normalize_mechanism_type(mech_type, original_json_type)
        return normalized_type in cls._registry

    @classmethod
    def _normalize_mechanism_type(cls, mech_type: str, original_json_type: str = None) -> str:
        """
        Normalize mechanism type strings to standard identifiers.

        Handles the various ways mechanism types can be specified
        (from UI, JSON, recommendations, etc.)
        """
        # Handle 4-bar linkage variations
        if mech_type in ["4-Bar Linkage", "4_bar_linkage"] or original_json_type == "4-bar Coupler":
            return "4_bar_linkage"

        # Handle gear variations
        elif mech_type in [
            "Gears (Simple Pair)",
            "Planetary Gear",
            "gear",
            "planetary_gear",
        ] or original_json_type in ["Simple Gear", "Gear Contact", "Planetary Gear"]:
            return "gear"

        # Handle cam variations
        elif mech_type in ["Cam & Follower", "cam", "cam_follower"] or original_json_type in [
            "Cam-Follower",
            "Cam Follower",
        ]:
            return "cam"

        # Handle belt variations
        elif mech_type in ["Belt", "belt", "belt_pulley", "Belt System"] or original_json_type in [
            "Belt System",
            "Pulley System",
        ]:
            return "belt"

        # Handle spring variations
        elif mech_type in [
            "Spring",
            "spring",
            "spring_damper",
            "Spring System",
        ] or original_json_type in ["Spring System", "Damper System"]:
            return "spring"

        # Default to original type
        return mech_type.lower() if mech_type else "unknown"


# Auto-registration function that will be called by mechanism modules
def auto_register_mechanisms():
    """
    Automatically register all available parametric mechanism implementations.

    This function is called on module import to populate the registry.
    Each mechanism module should call register_mechanism() during import.
    """
    try:
        # Import and register 4-bar linkage
        from .mechanisms.linkage_parametric import LinkageParametricEditor

        ParametricFactory.register_mechanism("4_bar_linkage", LinkageParametricEditor)
    except ImportError as e:
        logger.warning(f"Could not register linkage parametric editor: {e}")

    try:
        # Import and register gear
        from .mechanisms.gear_parametric import GearParametricEditor

        ParametricFactory.register_mechanism("gear", GearParametricEditor)
    except ImportError as e:
        logger.warning(f"Could not register gear parametric editor: {e}")

    try:
        # Import and register cam
        from .mechanisms.cam_parametric import CamParametricEditor

        ParametricFactory.register_mechanism("cam", CamParametricEditor)
    except ImportError as e:
        logger.warning(f"Could not register cam parametric editor: {e}")

    try:
        # Import and register belt
        from .mechanisms.belt_parametric import BeltParametricEditor

        ParametricFactory.register_mechanism("belt", BeltParametricEditor)
    except ImportError as e:
        logger.warning(f"Could not register belt parametric editor: {e}")

    try:
        # Import and register spring
        from .mechanisms.spring_parametric import SpringParametricEditor

        ParametricFactory.register_mechanism("spring", SpringParametricEditor)
    except ImportError as e:
        logger.warning(f"Could not register spring parametric editor: {e}")


# Call auto-registration on module import
auto_register_mechanisms()
