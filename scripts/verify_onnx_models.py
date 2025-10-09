#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _load_onnx_module():
    try:
        import onnx  # type: ignore
    except ImportError:
        logging.error(
            "onnx package not installed. Install with `uv pip install onnx` "
            "or `pip install onnx` and re-run."
        )
        return None
    return onnx


def verify_models(root: Path) -> int:
    onnx = _load_onnx_module()
    if onnx is None:
        return 2

    if not root.exists():
        logging.error("Model root %s does not exist.", root)
        return 1

    model_paths = sorted(root.glob("*.onnx"))
    if not model_paths:
        logging.warning("No .onnx files found under %s", root)
        return 0

    failures = 0
    for path in model_paths:
        try:
            model = onnx.load(path)
            onnx.checker.check_model(model)
            logging.info("OK  %s", path)
        except Exception as exc:
            failures += 1
            logging.error("FAIL %s :: %s", path, exc)

    if failures:
        logging.error("%d model(s) failed verification", failures)
    else:
        logging.info("All ONNX models verified successfully.")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ONNX model integrity.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("models/onnx"),
        help="Directory containing *.onnx models (default: models/onnx).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    sys.exit(verify_models(args.root))


if __name__ == "__main__":
    main()
