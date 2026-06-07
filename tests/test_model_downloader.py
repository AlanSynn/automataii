from __future__ import annotations

from pathlib import Path

from automataii.utils.model_downloader import ModelDownloader


def test_training_only_model_without_hosted_url_does_not_download(
    tmp_path: Path,
    monkeypatch,
) -> None:
    downloader = ModelDownloader(models_dir=tmp_path)
    called = False

    def fail_download(url: str, destination: Path, expected_size: int | None = None) -> bool:
        nonlocal called
        called = True
        raise AssertionError("stale training-only model URL should not be downloaded")

    monkeypatch.setattr(downloader, "_download_file", fail_download)

    assert downloader.download_model("detector_latest.pth") is None
    assert called is False


def test_existing_optional_model_is_reused_without_network(tmp_path: Path, monkeypatch) -> None:
    downloader = ModelDownloader(models_dir=tmp_path)
    local_weight = downloader.weights_dir / "detector_latest.pth"
    local_weight.write_bytes(b"local optional model")

    def fail_download(url: str, destination: Path, expected_size: int | None = None) -> bool:
        raise AssertionError("existing model should be verified/reused without network")

    monkeypatch.setattr(downloader, "_download_file", fail_download)

    assert downloader.download_model("detector_latest.pth") == local_weight
