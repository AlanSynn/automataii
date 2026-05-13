"""
Character Preset Service.

Application service for loading and managing character presets.
Provides access to preset definitions from the resources directory.

Architecture: Application Layer - Orchestrates domain objects and infrastructure.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

from automataii.domain.character import CharacterPreset, PresetPartData, SkeletonJoint


class CharacterPresetService:
    """Service for loading and managing character presets.

    Responsibilities:
    - Load presets from resources directory
    - Provide access to available presets
    - Cache loaded presets for performance
    """

    # Default presets directory relative to project root
    DEFAULT_PRESETS_PATH = Path("resources/presets/characters")

    def __init__(self, presets_path: Path | None = None):
        """Initialize the preset service.

        Args:
            presets_path: Optional custom path to presets directory.
                         Defaults to resources/presets/characters.
        """
        self._presets_path = presets_path or self._find_presets_path()
        self._cache: dict[str, CharacterPreset] = {}
        self._available_presets: list[str] = []
        self._loaded = False

    def _find_presets_path(self) -> Path:
        """Find the presets directory by searching common locations."""
        # Try relative to current file
        module_path = Path(__file__).parent.parent.parent.parent.parent
        candidate = module_path / "resources" / "presets" / "characters"
        if candidate.exists():
            return candidate

        # Try current working directory
        cwd_candidate = Path.cwd() / "resources" / "presets" / "characters"
        if cwd_candidate.exists():
            return cwd_candidate

        # Return default (may not exist)
        return self.DEFAULT_PRESETS_PATH

    def get_available_presets(self) -> Sequence[str]:
        """Get list of available preset IDs.

        Returns:
            Sequence of preset IDs that can be loaded.
        """
        if not self._loaded:
            self._scan_presets()
        return tuple(self._available_presets)

    def get_preset(self, preset_id: str) -> CharacterPreset | None:
        """Get a preset by ID.

        Args:
            preset_id: The preset identifier.

        Returns:
            The CharacterPreset if found, None otherwise.
        """
        # Check cache first
        if preset_id in self._cache:
            return self._cache[preset_id]

        # Try to load from disk
        preset = self._load_preset(preset_id)
        if preset:
            self._cache[preset_id] = preset
        return preset

    def get_default_preset(self) -> CharacterPreset:
        """Get the default silhouette human preset.

        Returns:
            The default CharacterPreset (silhouette_human).
        """
        preset = self.get_preset("silhouette_human")
        if preset:
            return preset

        # Fallback to factory method if file not found
        logging.warning("Silhouette preset file not found, using factory method")
        return CharacterPreset.create_silhouette_human()

    def get_preset_info(self, preset_id: str) -> dict | None:
        """Get basic info about a preset without fully loading it.

        Args:
            preset_id: The preset identifier.

        Returns:
            Dictionary with id, name, description, thumbnail_path, or None.
        """
        preset_dir = self._presets_path / preset_id
        preset_file = preset_dir / "preset.json"

        if not preset_file.exists():
            return None

        try:
            with open(preset_file, encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "id": data.get("id", preset_id),
                    "name": data.get("name", preset_id),
                    "description": data.get("description", ""),
                    "thumbnail_path": str(preset_dir / data.get("thumbnail_path", "thumbnail.svg")),
                }
        except (json.JSONDecodeError, OSError) as e:
            logging.warning(f"Failed to load preset info for {preset_id}: {e}")
            return None

    def _scan_presets(self) -> None:
        """Scan the presets directory for available presets."""
        self._available_presets.clear()

        if not self._presets_path.exists():
            logging.warning(f"Presets directory not found: {self._presets_path}")
            # Add built-in preset
            self._available_presets.append("silhouette_human")
            self._loaded = True
            return

        for entry in self._presets_path.iterdir():
            if entry.is_dir():
                preset_file = entry / "preset.json"
                if preset_file.exists():
                    self._available_presets.append(entry.name)

        # Ensure silhouette_human is always available
        if "silhouette_human" not in self._available_presets:
            self._available_presets.insert(0, "silhouette_human")

        self._loaded = True
        logging.info(f"Found {len(self._available_presets)} character presets")

    def _load_preset(self, preset_id: str) -> CharacterPreset | None:
        """Load a preset from the resources directory.

        Args:
            preset_id: The preset identifier.

        Returns:
            The loaded CharacterPreset, or None if not found.
        """
        preset_dir = self._presets_path / preset_id
        preset_file = preset_dir / "preset.json"

        if not preset_file.exists():
            logging.warning(f"Preset file not found: {preset_file}")
            # Fallback to factory method for silhouette_human
            if preset_id == "silhouette_human":
                return CharacterPreset.create_silhouette_human()
            return None

        try:
            with open(preset_file, encoding="utf-8") as f:
                data = json.load(f)

            # Parse parts
            parts: dict[str, PresetPartData] = {}
            for name, pdata in data.get("parts", {}).items():
                # Resolve relative paths
                svg_path = str(preset_dir / pdata.get("svg_path", ""))
                parts[name] = PresetPartData(
                    name=pdata["name"],
                    svg_path=svg_path,
                    anchor_joint=pdata["anchor_joint"],
                    z_index=pdata.get("z_index", 0),
                    default_transform=tuple(pdata.get("default_transform", [0, 0, 0])),
                )

            # Parse skeleton
            skeleton: dict[str, SkeletonJoint] = {}
            for jid, jdata in data.get("skeleton", {}).items():
                skeleton[jid] = SkeletonJoint(
                    id=jdata["id"],
                    parent_id=jdata.get("parent_id"),
                    position=tuple(jdata.get("position", [0, 0])),
                    children=tuple(jdata.get("children", [])),
                )

            # Resolve thumbnail path
            thumbnail = data.get("thumbnail_path")
            if thumbnail:
                thumbnail = str(preset_dir / thumbnail)

            return CharacterPreset(
                id=data["id"],
                name=data["name"],
                parts=parts,
                skeleton=skeleton,
                thumbnail_path=thumbnail,
                description=data.get("description", ""),
            )

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logging.error(f"Failed to load preset {preset_id}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the preset cache."""
        self._cache.clear()

    def reload(self) -> None:
        """Reload all presets from disk."""
        self.clear_cache()
        self._loaded = False
        self._scan_presets()
