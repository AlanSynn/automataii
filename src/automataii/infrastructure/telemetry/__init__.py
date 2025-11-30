"""
Telemetry Infrastructure.

Provides observability through structured logging and span tracking.

Usage:
    from automataii.infrastructure.telemetry import telemetry_span

    with telemetry_span("operation_name", field1=value1) as span:
        # Do work
        span.set(result="success")
"""

from automataii.infrastructure.telemetry.telemetry import TelemetrySpan, telemetry_span

__all__ = [
    "TelemetrySpan",
    "telemetry_span",
]
