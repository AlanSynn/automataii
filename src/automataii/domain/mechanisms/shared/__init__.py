"""
Shared domain utilities for mechanism analysis.

This module provides reusable functions and classes for mechanism
analysis that are used across different mechanism types (fourbar,
fivebar, sixbar, etc.).
"""

from automataii.domain.mechanisms.shared.transmission_analyzer import (
    TransmissionAngleQuality,
    TransmissionAngleResult,
    calculate_transmission_angle,
    classify_transmission_angle,
    analyze_joint_angle,
    analyze_link_ratios,
    EXCELLENT_RANGE,
    GOOD_RANGE,
    POOR_RANGE,
)

__all__ = [
    "TransmissionAngleQuality",
    "TransmissionAngleResult",
    "calculate_transmission_angle",
    "classify_transmission_angle",
    "analyze_joint_angle",
    "analyze_link_ratios",
    "EXCELLENT_RANGE",
    "GOOD_RANGE",
    "POOR_RANGE",
]
