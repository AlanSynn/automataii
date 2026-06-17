"""Small stdlib download helper for build scripts."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen


def download_file(url: str, destination: Path, chunk_size: int = 8192) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response, destination.open("wb") as output:  # noqa: S310 - release URLs are fixed by build scripts.
        while chunk := response.read(chunk_size):
            output.write(chunk)
    return destination
