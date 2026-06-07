"""
Model downloader utility for MotionSmith.

Runtime image processing uses bundled ONNX models.  The legacy PyTorch weights
listed here are training/fine-tuning artifacts only; when they are not hosted we
must not hit stale release URLs during a production run.
"""

import hashlib
import logging
from pathlib import Path
from typing import ClassVar, TypedDict

logger = logging.getLogger(__name__)


class ModelInfo(TypedDict):
    """Metadata for an optional model artifact."""

    url: str | None
    sha256: str
    size: int
    description: str


class ModelDownloader:
    """Download optional, non-runtime model files on demand."""

    # These large PyTorch weights are excluded from the distribution.  The
    # production runtime should use bundled ONNX models instead, so keep URLs as
    # None until a real hosted artifact and checksum exist.
    MODEL_URLS: ClassVar[dict[str, ModelInfo]] = {
        "detector_latest.pth": {
            "url": None,
            "sha256": "placeholder_hash_detector",
            "size": 400_000_000,
            "description": "PyTorch detection model weights (training/fine-tuning only)",
        },
        "pose_best_AP_epoch_72.pth": {
            "url": None,
            "sha256": "placeholder_hash_pose",
            "size": 300_000_000,
            "description": "PyTorch pose estimation model weights (training/fine-tuning only)",
        },
    }

    def __init__(self, models_dir: Path | None = None) -> None:
        """Initialize with models directory."""
        if models_dir is None:
            # Use project root to find models directory.
            from .paths import get_project_root

            project_root = get_project_root()
            self.models_dir = project_root / "models"
        else:
            self.models_dir = Path(models_dir)

        self.weights_dir = self.models_dir / "weights"
        self.weights_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _download_file(
        self,
        url: str,
        destination: Path,
        expected_size: int | None = None,
    ) -> bool:
        """Download a file with progress logging."""
        try:
            import requests  # type: ignore[import-untyped]

            logger.info("Downloading %s from %s", destination.name, url)

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            if expected_size and total_size and total_size != expected_size:
                logger.warning("Size mismatch: expected %s, got %s", expected_size, total_size)

            downloaded = 0
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log progress every 10MB.
                        if downloaded % (10 * 1024 * 1024) == 0 and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            logger.info("Download progress: %.1f%%", progress)

            logger.info("Download completed: %s", destination)
            return True

        except Exception as e:
            logger.error("Download failed: %s", e)
            if destination.exists():
                destination.unlink()  # Remove partial download.
            return False

    def _verify_file(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify file integrity using SHA256."""
        if not file_path.exists():
            return False

        # Skip verification if hash is placeholder.
        if expected_sha256.startswith("placeholder_"):
            logger.warning("Skipping hash verification for %s (placeholder hash)", file_path.name)
            return True

        try:
            actual_sha256 = self._calculate_sha256(file_path)
            if actual_sha256 == expected_sha256:
                logger.info("File verification successful: %s", file_path.name)
                return True
            logger.error("File verification failed: %s", file_path.name)
            logger.error("Expected: %s", expected_sha256)
            logger.error("Actual: %s", actual_sha256)
            return False
        except Exception as e:
            logger.error("Verification error: %s", e)
            return False

    def download_model(self, model_name: str, force_download: bool = False) -> Path | None:
        """Download a specific optional model file if a hosted artifact exists."""
        model_info = self.MODEL_URLS.get(model_name)
        if model_info is None:
            logger.error("Unknown model: %s", model_name)
            return None

        file_path = self.weights_dir / model_name

        # Check if file already exists and is valid.
        if file_path.exists() and not force_download:
            if self._verify_file(file_path, model_info["sha256"]):
                logger.info("Model already exists and is valid: %s", model_name)
                return file_path
            logger.warning("Existing model file is corrupted, re-downloading: %s", model_name)

        url = model_info["url"]
        if url is None:
            logger.warning(
                "%s is not hosted for automatic download; runtime inference uses bundled ONNX models.",
                model_name,
            )
            return None

        # Download the file.
        if not self._download_file(url, file_path, model_info["size"]):
            logger.error("Failed to download model: %s", model_name)
            return None

        # Verify the downloaded file.
        if self._verify_file(file_path, model_info["sha256"]):
            return file_path

        logger.error("Downloaded file verification failed: %s", model_name)
        if file_path.exists():
            file_path.unlink()
        return None
