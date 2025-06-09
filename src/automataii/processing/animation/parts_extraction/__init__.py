"""Parts extraction module for body part segmentation and extraction."""

from .extractor import BodyPartsExtractor
from .models import PartInfo, ExtractionResult

__all__ = ["BodyPartsExtractor", "PartInfo", "ExtractionResult"]