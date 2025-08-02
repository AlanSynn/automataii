"""
Model downloader utility for Automataii
Downloads large model files on-demand when not included in the distribution
"""

import hashlib
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class ModelDownloader:
    """Downloads model files on-demand"""

    # Model file URLs and checksums
    # Note: These models are large PyTorch weights excluded from the main distribution
    # The actual ONNX models are included in the build for runtime inference
    MODEL_URLS = {
        "detector_latest.pth": {
            "url": "https://github.com/alansynn/automataii/releases/download/models-v1.0/detector_latest.pth",
            "sha256": "placeholder_hash_detector",  # Update with actual hash when hosting
            "size": 400_000_000,  # ~400MB
            "description": "PyTorch detection model weights (training/fine-tuning only)",
        },
        "pose_best_AP_epoch_72.pth": {
            "url": "https://github.com/alansynn/automataii/releases/download/models-v1.0/pose_best_AP_epoch_72.pth",
            "sha256": "placeholder_hash_pose",  # Update with actual hash when hosting
            "size": 300_000_000,  # ~300MB
            "description": "PyTorch pose estimation model weights (training/fine-tuning only)",
        },
    }

    def __init__(self, models_dir: Path | None = None):
        """Initialize with models directory"""
        if models_dir is None:
            # Use project root to find models directory
            from .paths import get_project_root

            project_root = get_project_root()
            self.models_dir = project_root / "models"
        else:
            self.models_dir = Path(models_dir)

        self.weights_dir = self.models_dir / "weights"
        self.weights_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _download_file(self, url: str, destination: Path, expected_size: int = None) -> bool:
        """Download a file with progress logging"""
        try:
            logger.info(f"Downloading {destination.name} from {url}")

            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            if expected_size and total_size != expected_size:
                logger.warning(f"Size mismatch: expected {expected_size}, got {total_size}")

            downloaded = 0
            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log progress every 10MB
                        if downloaded % (10 * 1024 * 1024) == 0:
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                logger.info(f"Download progress: {progress:.1f}%")

            logger.info(f"Download completed: {destination}")
            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            if destination.exists():
                destination.unlink()  # Remove partial download
            return False

    def _verify_file(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify file integrity using SHA256"""
        if not file_path.exists():
            return False

        # Skip verification if hash is placeholder
        if expected_sha256.startswith("placeholder_"):
            logger.warning(f"Skipping hash verification for {file_path.name} (placeholder hash)")
            return True

        try:
            actual_sha256 = self._calculate_sha256(file_path)
            if actual_sha256 == expected_sha256:
                logger.info(f"File verification successful: {file_path.name}")
                return True
            else:
                logger.error(f"File verification failed: {file_path.name}")
                logger.error(f"Expected: {expected_sha256}")
                logger.error(f"Actual: {actual_sha256}")
                return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    def download_model(self, model_name: str, force_download: bool = False) -> Path | None:
        """Download a specific model file if needed"""
        if model_name not in self.MODEL_URLS:
            logger.error(f"Unknown model: {model_name}")
            return None

        model_info = self.MODEL_URLS[model_name]
        file_path = self.weights_dir / model_name

        # Check if file already exists and is valid
        if file_path.exists() and not force_download:
            if self._verify_file(file_path, model_info["sha256"]):
                logger.info(f"Model already exists and is valid: {model_name}")
                return file_path
            else:
                logger.warning(f"Existing model file is corrupted, re-downloading: {model_name}")

        # Download the file
        if self._download_file(model_info["url"], file_path, model_info["size"]):
            # Verify the downloaded file
            if self._verify_file(file_path, model_info["sha256"]):
                return file_path
            else:
                logger.error(f"Downloaded file verification failed: {model_name}")
                if file_path.exists():
                    file_path.unlink()
                return None
        else:
            logger.error(f"Failed to download model: {model_name}")
            return None

    def ensure_model_available(self, model_name: str) -> Path:
        """Ensure a model is available, downloading if necessary"""
        file_path = self.weights_dir / model_name

        # If file exists and is valid, return it
        if file_path.exists():
            model_info = self.MODEL_URLS.get(model_name)
            if model_info and self._verify_file(file_path, model_info["sha256"]):
                return file_path

        # Try to download
        downloaded_path = self.download_model(model_name)
        if downloaded_path:
            return downloaded_path
        else:
            raise FileNotFoundError(f"Could not obtain model file: {model_name}")

    def check_available_models(self) -> dict:
        """Check which models are available locally"""
        available = {}
        for model_name in self.MODEL_URLS:
            file_path = self.weights_dir / model_name
            if file_path.exists():
                try:
                    model_info = self.MODEL_URLS[model_name]
                    is_valid = self._verify_file(file_path, model_info["sha256"])
                    available[model_name] = {
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "valid": is_valid,
                    }
                except Exception as e:
                    available[model_name] = {
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "valid": False,
                        "error": str(e),
                    }
        return available


# Convenience function for easy access
def get_model_path(model_name: str) -> Path:
    """Get path to a model file, downloading if necessary"""
    downloader = ModelDownloader()
    return downloader.ensure_model_available(model_name)
