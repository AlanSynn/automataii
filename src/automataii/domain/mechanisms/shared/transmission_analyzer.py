"""
Transmission Angle Analysis for Linkage Mechanisms.

This module provides shared utilities for analyzing transmission angles
in various linkage mechanisms (fourbar, fivebar, sixbar, etc.).

Transmission angle is the angle between the coupler and output link,
which affects the mechanical efficiency of force transmission.

Optimal Range: 40° - 140° (90° is ideal)
Acceptable Range: 20° - 160°
Critical (lock-up): < 20° or > 160°

Time Complexity: O(1) for all operations
Space Complexity: O(1)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

# Quality thresholds (degrees)
EXCELLENT_RANGE = (40.0, 140.0)  # Ideal mechanical advantage
GOOD_RANGE = (30.0, 150.0)  # Acceptable performance
POOR_RANGE = (20.0, 160.0)  # Degraded but functional
# Outside POOR_RANGE = Critical (near lock-up)


class TransmissionAngleQuality(Enum):
    """Quality classification for transmission angles."""

    EXCELLENT = "excellent"
    GOOD = "good"
    POOR = "poor"
    CRITICAL = "critical"
    IMPOSSIBLE = "impossible"
    UNKNOWN = "unknown"


class TransmissionAngleResult(NamedTuple):
    """Result of transmission angle analysis.

    Attributes:
        angle_deg: The transmission angle in degrees (0-180)
        quality: Quality classification
        message: Human-readable description
    """

    angle_deg: float
    quality: TransmissionAngleQuality
    message: str


def calculate_transmission_angle(
    dist_coupler_output: float,
    coupler_length: float,
    output_length: float,
) -> float | None:
    """Calculate transmission angle using law of cosines.

    The transmission angle (gamma) is the angle at the coupler-output joint.
    Uses the law of cosines: cos(γ) = (a² + b² - c²) / (2ab)

    Args:
        dist_coupler_output: Distance between coupler joint and output pivot
        coupler_length: Length of the coupler link
        output_length: Length of the output link

    Returns:
        Transmission angle in degrees (0-180), or None if geometry is invalid

    Example:
        >>> angle = calculate_transmission_angle(100.0, 80.0, 60.0)
        >>> print(f"Transmission angle: {angle:.1f}°")
    """
    if coupler_length <= 0 or output_length <= 0:
        return None

    # Check if triangle inequality is satisfied
    max_reach = coupler_length + output_length
    min_reach = abs(coupler_length - output_length)

    if dist_coupler_output > max_reach or dist_coupler_output < min_reach:
        return None

    try:
        # Law of cosines: cos(γ) = (c² + o² - d²) / (2co)
        # where c=coupler, o=output, d=distance
        cos_gamma = (coupler_length**2 + output_length**2 - dist_coupler_output**2) / (
            2 * coupler_length * output_length
        )

        # Clamp to valid range for acos (numerical stability)
        cos_gamma = max(-1.0, min(1.0, cos_gamma))

        # Return absolute angle (always positive, 0-180°)
        return math.degrees(math.acos(abs(cos_gamma)))

    except (ValueError, ZeroDivisionError):
        return None


def classify_transmission_angle(angle_deg: float | None) -> TransmissionAngleResult:
    """Classify transmission angle quality.

    Args:
        angle_deg: Transmission angle in degrees, or None if invalid

    Returns:
        TransmissionAngleResult with quality classification and message
    """
    if angle_deg is None:
        return TransmissionAngleResult(
            angle_deg=0.0,
            quality=TransmissionAngleQuality.IMPOSSIBLE,
            message="Invalid geometry: cannot form mechanism",
        )

    if EXCELLENT_RANGE[0] <= angle_deg <= EXCELLENT_RANGE[1]:
        return TransmissionAngleResult(
            angle_deg=angle_deg,
            quality=TransmissionAngleQuality.EXCELLENT,
            message=f"Excellent transmission angle: {angle_deg:.1f}°",
        )

    if GOOD_RANGE[0] <= angle_deg <= GOOD_RANGE[1]:
        return TransmissionAngleResult(
            angle_deg=angle_deg,
            quality=TransmissionAngleQuality.GOOD,
            message=f"Good transmission angle: {angle_deg:.1f}°",
        )

    if POOR_RANGE[0] <= angle_deg <= POOR_RANGE[1]:
        return TransmissionAngleResult(
            angle_deg=angle_deg,
            quality=TransmissionAngleQuality.POOR,
            message=f"Poor transmission angle: {angle_deg:.1f}° (reduced efficiency)",
        )

    # Critical - near lock-up condition
    return TransmissionAngleResult(
        angle_deg=angle_deg,
        quality=TransmissionAngleQuality.CRITICAL,
        message=f"Critical transmission angle: {angle_deg:.1f}° (near lock-up)",
    )


def analyze_joint_angle(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> TransmissionAngleResult:
    """Analyze the angle at joint p2 formed by p1-p2-p3.

    Calculates the angle at the middle point using vector dot product.
    Useful for analyzing transmission angles at arbitrary joints.

    Args:
        p1: First point coordinates (x, y)
        p2: Middle point (joint) coordinates (x, y)
        p3: Third point coordinates (x, y)

    Returns:
        TransmissionAngleResult with angle and quality classification

    Example:
        >>> result = analyze_joint_angle((0, 0), (50, 50), (100, 0))
        >>> print(f"Joint angle: {result.angle_deg:.1f}° ({result.quality.value})")
    """
    # Vectors from p2 to p1 and p2 to p3
    v1 = (p1[0] - p2[0], p1[1] - p2[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])

    # Vector lengths
    len1 = math.hypot(v1[0], v1[1])
    len2 = math.hypot(v2[0], v2[1])

    if len1 < 1e-10 or len2 < 1e-10:
        return TransmissionAngleResult(
            angle_deg=0.0,
            quality=TransmissionAngleQuality.UNKNOWN,
            message="Degenerate joint: zero-length link",
        )

    # Dot product and angle calculation
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cos_angle = max(-1.0, min(1.0, dot / (len1 * len2)))

    try:
        angle_deg = math.degrees(math.acos(cos_angle))
        return classify_transmission_angle(angle_deg)
    except ValueError:
        return TransmissionAngleResult(
            angle_deg=0.0,
            quality=TransmissionAngleQuality.UNKNOWN,
            message="Could not compute joint angle",
        )


@dataclass(frozen=True)
class LinkRatioResult:
    """Result of link ratio analysis.

    Attributes:
        max_ratio: Maximum link length ratio (longest/shortest)
        quality: Quality classification string
        message: Human-readable description
    """

    max_ratio: float
    quality: str
    message: str


def analyze_link_ratios(
    link_lengths: list[float],
    max_acceptable_ratio: float = 10.0,
    warning_ratio: float = 6.0,
) -> LinkRatioResult:
    """Analyze link length ratios for mechanism quality.

    Extreme ratios between link lengths can cause:
    - Poor force transmission
    - Increased wear
    - Potential for binding or jamming

    Args:
        link_lengths: List of link lengths
        max_acceptable_ratio: Ratio above which quality is "poor"
        warning_ratio: Ratio above which quality is "fair"

    Returns:
        LinkRatioResult with ratio and quality assessment

    Example:
        >>> result = analyze_link_ratios([50, 60, 80, 100])
        >>> print(f"Link ratio: {result.max_ratio:.1f}:1 ({result.quality})")
    """
    if not link_lengths:
        return LinkRatioResult(max_ratio=0.0, quality="unknown", message="No link lengths provided")

    # Filter out invalid lengths
    valid_lengths = [length for length in link_lengths if length > 0]

    if len(valid_lengths) < 2:
        return LinkRatioResult(
            max_ratio=0.0, quality="unknown", message="Insufficient valid link lengths"
        )

    min_length = min(valid_lengths)
    max_length = max(valid_lengths)
    max_ratio = max_length / min_length

    if max_ratio > max_acceptable_ratio:
        return LinkRatioResult(
            max_ratio=max_ratio,
            quality="poor",
            message=f"Extreme link ratio: {max_ratio:.1f}:1 (may cause binding)",
        )

    if max_ratio > warning_ratio:
        return LinkRatioResult(
            max_ratio=max_ratio,
            quality="fair",
            message=f"High link ratio: {max_ratio:.1f}:1 (reduced efficiency)",
        )

    return LinkRatioResult(
        max_ratio=max_ratio, quality="excellent", message=f"Good link ratios: {max_ratio:.1f}:1"
    )
