import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

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
        mechanism_key = self._safe_mechanism_key(mechanism_type)
        if mechanism_key in self._cache:
            return self._cache[mechanism_key]

        content_file = self.content_dir / f"{mechanism_key}.json"

        if not content_file.exists():
            content = self._create_default_content(mechanism_key)
            self._cache[mechanism_key] = content
            return content

        try:
            with open(content_file, encoding="utf-8") as f:
                data = json.load(f)

            content = self._parse_content(data)
            self._cache[mechanism_key] = content
            return content

        except (json.JSONDecodeError, KeyError, ValueError, TypeError, OSError) as e:
            logger.error(f"Error loading content for {mechanism_key}: {e}")
            content = self._create_default_content(mechanism_key)
            self._cache[mechanism_key] = content
            return content

    @staticmethod
    def _safe_mechanism_key(mechanism_type: object) -> str:
        key = str(mechanism_type or "unknown").strip()
        safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in key)
        return safe.strip("._-") or "unknown"

    @staticmethod
    def _safe_text(value: object, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    @classmethod
    def _safe_text_tuple(cls, value: object) -> tuple[str, ...]:
        values: tuple[object, ...]
        if value is None:
            return ()
        if isinstance(value, str):
            values = (value,)
        else:
            try:
                values = tuple(value)  # type: ignore[arg-type]
            except TypeError:
                values = (value,)
        return tuple(text for item in values if (text := cls._safe_text(item)))

    @staticmethod
    def _safe_option_value(value: object) -> float | None:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _parse_parameter_options(
        cls, raw_options: object
    ) -> dict[str, tuple[ParameterOption, ...]]:
        if not isinstance(raw_options, dict):
            return {}

        param_options: dict[str, tuple[ParameterOption, ...]] = {}
        for key, options in raw_options.items():
            if not isinstance(options, list | tuple):
                continue
            parsed: list[ParameterOption] = []
            for opt in options:
                if not isinstance(opt, dict):
                    continue
                value = cls._safe_option_value(opt.get("value"))
                label = cls._safe_text(opt.get("label"))
                if value is None or not label:
                    continue
                description = opt.get("description")
                parsed.append(
                    ParameterOption(
                        value=value,
                        label=label,
                        description=cls._safe_text(description)
                        if description is not None
                        else None,
                    )
                )
            if parsed:
                param_options[cls._safe_text(key, "parameter")] = tuple(parsed)
        return param_options

    def _parse_content(self, data: object) -> MechanismContent:
        if not isinstance(data, dict):
            raise ValueError("content root must be an object")

        param_options = self._parse_parameter_options(data.get("parameter_options", {}))

        tags = self._safe_text_tuple(data.get("tags", ()))
        motions_raw = self._safe_text_tuple(data.get("motions", ()))
        motions = motions_raw or self._derive_motions(tags)
        gallery_summary = data.get("gallery_summary")
        diagram_path = data.get("diagram_path")

        return MechanismContent(
            title=self._safe_text(data.get("title"), "Untitled Mechanism"),
            goal=self._safe_text(data.get("goal"), "No description available"),
            parts=self._safe_text_tuple(data.get("parts", ())),
            advantages=self._safe_text_tuple(data.get("advantages", ())),
            disadvantages=self._safe_text_tuple(data.get("disadvantages", ())),
            materials=self._safe_text_tuple(data.get("materials", ())),
            cautions=self._safe_text_tuple(data.get("cautions", ())),
            parameter_options=param_options,
            diagram_path=self._safe_text(diagram_path) if diagram_path is not None else None,
            tags=tags,
            motions=motions,
            gallery_summary=self._safe_text(gallery_summary)
            if gallery_summary is not None
            else None,
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

        try:
            return sorted(f.stem for f in self.content_dir.glob("*.json") if f.is_file())
        except OSError:
            return []
