"""
Telemetry Implementation.

Provides observability through structured logging and span tracking.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


def _is_enabled() -> bool:
    flag = os.getenv("AUTOMATAII_TELEMETRY", "1").lower()
    return flag not in {"0", "false", "off"}


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


@dataclass
class TelemetrySpan:
    """
    A telemetry span for measuring operation duration and logging.

    Usage:
        with TelemetrySpan("operation_name", field1=value1) as span:
            # Do work
            span.set(result="success")
    """
    name: str
    fields: dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("automataii.telemetry")
    )

    def __post_init__(self) -> None:
        self._enabled = _is_enabled()
        self._start: float | None = None

    def __enter__(self) -> TelemetrySpan:
        if self._enabled:
            self._start = time.perf_counter()
            self.logger.info(
                "telemetry_start %s",
                _serialize({"event": self.name, **self.fields}),
            )
        return self

    def set(self, **fields: Any) -> None:
        """Set additional fields on the span."""
        if self._enabled:
            self.fields.update({k: v for k, v in fields.items() if v is not None})

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._enabled:
            duration_ms = None
            if self._start is not None:
                duration_ms = round((time.perf_counter() - self._start) * 1000, 3)
                self.fields.setdefault("duration_ms", duration_ms)

            if exc_val:
                self.fields.setdefault("status", "error")
                self.fields.setdefault("error", repr(exc_val))
                level = logging.ERROR
            else:
                self.fields.setdefault("status", "ok")
                level = logging.INFO

            self.logger.log(
                level,
                "telemetry_end %s",
                _serialize({"event": self.name, **self.fields}),
            )
        return False


@contextmanager
def telemetry_span(name: str, **fields: Any):
    """
    Context manager for creating a telemetry span.

    Args:
        name: Name of the operation being measured
        **fields: Additional fields to log with the span

    Yields:
        TelemetrySpan instance for setting additional fields
    """
    span = TelemetrySpan(name=name, fields=fields)
    span.__enter__()
    try:
        yield span
    except Exception:
        exc_type, exc_val, exc_tb = sys.exc_info()
        span.__exit__(exc_type, exc_val, exc_tb)
        raise
    else:
        span.__exit__(None, None, None)
