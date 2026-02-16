import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParameterOption:
    value: float
    label: str
    description: str | None = None


@dataclass(frozen=True)
class MechanismContent:
    title: str
    goal: str
    parts: tuple[str, ...]
    advantages: tuple[str, ...]
    disadvantages: tuple[str, ...]
    materials: tuple[str, ...]
    cautions: tuple[str, ...]
    parameter_options: dict[str, tuple[ParameterOption, ...]]
    diagram_path: str | None
    tags: tuple[str, ...]
    motions: tuple[str, ...] = ()
    gallery_summary: str | None = None


class ContentLoader:
    def __init__(self, content_dir: Path | None = None):
        if content_dir is None:
            base_path = Path(__file__).parent.parent.parent.parent.parent
            content_dir = base_path / "resources" / "mechanism_content"

        self.content_dir = Path(content_dir)
        self._cache: dict[str, MechanismContent] = {}

    def load_content(self, mechanism_type: str) -> MechanismContent:
        if mechanism_type in self._cache:
            return self._cache[mechanism_type]

        content_file = self.content_dir / f"{mechanism_type}.json"

        if not content_file.exists():
            return self._create_default_content(mechanism_type)

        try:
            with open(content_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            content = self._parse_content(data)
            self._cache[mechanism_type] = content
            return content

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error loading content for {mechanism_type}: {e}")
            return self._create_default_content(mechanism_type)

    def _parse_content(self, data: dict[str, Any]) -> MechanismContent:
        param_options = {}
        for key, options in data.get("parameter_options", {}).items():
            param_options[key] = tuple(
                ParameterOption(
                    value=opt["value"], label=opt["label"], description=opt.get("description")
                )
                for opt in options
            )

        tags = tuple(data.get("tags", []))
        motions_raw = tuple(data.get("motions", []))
        motions = motions_raw or self._derive_motions(tags)
        gallery_summary = data.get("gallery_summary")

        return MechanismContent(
            title=data["title"],
            goal=data["goal"],
            parts=tuple(data.get("parts", [])),
            advantages=tuple(data.get("advantages", [])),
            disadvantages=tuple(data.get("disadvantages", [])),
            materials=tuple(data.get("materials", [])),
            cautions=tuple(data.get("cautions", [])),
            parameter_options=param_options,
            diagram_path=data.get("diagram_path"),
            tags=tags,
            motions=motions,
            gallery_summary=gallery_summary,
        )

    def _create_default_content(self, mechanism_type: str) -> MechanismContent:
        return MechanismContent(
            title=mechanism_type.replace("_", " ").title(),
            goal="No description available",
            parts=(),
            advantages=(),
            disadvantages=(),
            materials=(),
            cautions=(),
            parameter_options={},
            diagram_path=None,
            tags=(),
            motions=(),
            gallery_summary=None,
        )

    @staticmethod
    def _derive_motions(tags: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {str(tag).strip().lower() for tag in tags}
        motions: list[str] = []

        if "rotary" in normalized:
            motions.append("Circular")
        if "oscillating" in normalized:
            motions.append("Oscillatory")
        if "linear" in normalized or "reciprocating" in normalized:
            motions.append("Linear")
        if "intermittent" in normalized:
            motions.append("Intermittent")

        return tuple(dict.fromkeys(motions))

    def list_available_content(self) -> list[str]:
        if not self.content_dir.exists():
            return []

        return [f.stem for f in self.content_dir.glob("*.json") if f.is_file()]
